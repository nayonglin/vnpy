from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage140_full_market_product_fit_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage140_full_market_product_fit_audit"

STRUCTURAL_AUDIT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_audit_full_market_structural_prefilter_v1.csv"
)
SUITABILITY_PREDICTIONS_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)
MARKET_DAILY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_market_daily_product_suitability_full_market_wf_v1.csv"
)
STAGE78_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv"
)
STAGE78_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv"
)
STAGE78_PRODUCT_ATTRIBUTION_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_full_product_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
STAGE78_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

PRODUCT_SCORE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_scores_{MODEL_TAG}.csv"
LAYER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_layer_summary_{MODEL_TAG}.csv"
ORIGIN_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_origin_summary_{MODEL_TAG}.csv"
TOP_CANDIDATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_candidates_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _rank_pct(series: pd.Series, high_is_good: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if not high_is_good:
        numeric = -numeric
    ranked = numeric.rank(pct=True, method="average")
    return ranked.fillna(0.0)


def _bounded_score(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(0.0, 1.0)


def _classification_reason(row: pd.Series) -> str:
    if int(row.get("eligible", 0)) != 1:
        return "数据或交易元信息不可用，不能进入适配池"
    if int(row.get("structural_prefilter_kept", 0)) != 1:
        return "全市场结构预筛未通过，先不做交易化"
    if row["fit_layer"] == "core_candidate":
        return "结构、AI机制分、样本外证据同时处于较高区间"
    if row["fit_layer"] == "satellite_candidate":
        return "结构或样本外证据较好，但仍需要影子观察确认"
    if row["fit_layer"] == "watchlist":
        return "有单项亮点，但结构和证据未形成共振"
    return "结构与证据均不足，或存在承载/成本缺陷"


def _origin_group(row: pd.Series) -> str:
    if bool(row.get("is_fu_satellite", False)):
        return "fu_satellite"
    if bool(row.get("is_manual_static18", False)):
        return "manual_static18"
    if bool(row.get("is_stage78_ai_selected", False)):
        return "stage78_ai_selected_nonstatic"
    if bool(row.get("eligible", 0)):
        return "full_market_other_eligible"
    return "full_market_ineligible"


def _calc_correlation_features(market_daily: pd.DataFrame, stage78_products: set[str]) -> pd.DataFrame:
    if market_daily.empty:
        return pd.DataFrame(
            columns=[
                "product_vt_symbol",
                "avg_abs_corr_to_stage78",
                "avg_abs_corr_to_all",
                "max_abs_corr_to_stage78",
            ]
        )

    frame = market_daily[["date", "product_vt_symbol", "close"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "product_vt_symbol", "close"])
    pivot = frame.pivot_table(index="date", columns="product_vt_symbol", values="close", aggfunc="last").sort_index()
    returns = pivot.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    returns = returns.dropna(how="all")
    if returns.shape[1] < 2:
        return pd.DataFrame(columns=["product_vt_symbol", "avg_abs_corr_to_stage78", "avg_abs_corr_to_all"])

    corr = returns.corr(min_periods=120).abs()
    records: list[dict[str, Any]] = []
    for product in corr.columns:
        peers = corr.loc[product].drop(labels=[product], errors="ignore").dropna()
        stage78_peers = [peer for peer in stage78_products if peer in peers.index and peer != product]
        stage78_corr = peers.loc[stage78_peers] if stage78_peers else pd.Series(dtype=float)
        records.append(
            {
                "product_vt_symbol": product,
                "avg_abs_corr_to_stage78": float(stage78_corr.mean()) if not stage78_corr.empty else 0.0,
                "avg_abs_corr_to_all": float(peers.mean()) if not peers.empty else 0.0,
                "max_abs_corr_to_stage78": float(stage78_corr.max()) if not stage78_corr.empty else 0.0,
            }
        )
    return pd.DataFrame(records)


def _build_ai_eligibility_summary(eligibility: pd.DataFrame) -> pd.DataFrame:
    frame = eligibility.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(frame, ["score", "score_rank", "top_n"])
    frame["is_static_boundary"] = frame["score_type"].astype(str).str.contains("static18_pre_ai_boundary", na=False)
    ai_frame = frame[~frame["is_static_boundary"]].copy()
    if ai_frame.empty:
        return pd.DataFrame(
            columns=[
                "product_vt_symbol",
                "stage78_ai_selected_count",
                "stage78_ai_eval_month_count",
                "stage78_ai_selected_frequency_pct",
                "stage78_ai_mean_rank",
                "stage78_ai_best_rank",
            ]
        )
    monthly_count = max(1, ai_frame["eval_date"].nunique())
    summary = (
        ai_frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            stage78_ai_selected_count=("eval_date", "count"),
            stage78_ai_mean_rank=("score_rank", "mean"),
            stage78_ai_best_rank=("score_rank", "min"),
            stage78_ai_mean_score=("score", "mean"),
        )
        .sort_values("stage78_ai_selected_count", ascending=False)
    )
    summary["stage78_ai_eval_month_count"] = monthly_count
    summary["stage78_ai_selected_frequency_pct"] = summary["stage78_ai_selected_count"] / monthly_count * 100.0
    return summary.reset_index(drop=True)


def _build_prediction_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    frame = predictions.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(
        frame,
        [
            "predicted_product_suitability_probability",
            "simple_trend_suitability_score_percentile",
            "future_net_pnl_60d",
            "future_rank_centered_60d",
            "target_future_top_half_60d",
        ],
    )
    frame["ai_rank"] = frame.groupby("eval_date")["predicted_product_suitability_probability"].rank(
        ascending=False, method="first"
    )
    frame["ai_top5"] = (frame["ai_rank"] <= 5).astype(int)
    frame["ai_top8"] = (frame["ai_rank"] <= 8).astype(int)
    frame["future_positive"] = (frame["future_net_pnl_60d"] > 0).astype(int)
    summary = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            wf_eval_count=("eval_date", "count"),
            mean_ai_probability=("predicted_product_suitability_probability", "mean"),
            median_ai_probability=("predicted_product_suitability_probability", "median"),
            median_simple_trend_score_pct=("simple_trend_suitability_score_percentile", "median"),
            ai_top5_frequency_pct=("ai_top5", lambda s: float(s.mean() * 100.0)),
            ai_top8_frequency_pct=("ai_top8", lambda s: float(s.mean() * 100.0)),
            future_60d_total_net_pnl=("future_net_pnl_60d", "sum"),
            future_60d_mean_net_pnl=("future_net_pnl_60d", "mean"),
            future_60d_positive_rate_pct=("future_positive", lambda s: float(s.mean() * 100.0)),
            future_60d_top_half_rate_pct=("target_future_top_half_60d", lambda s: float(s.mean() * 100.0)),
            future_60d_mean_rank_centered=("future_rank_centered_60d", "mean"),
        )
        .reset_index(drop=True)
    )
    return summary


def _build_product_scores() -> tuple[pd.DataFrame, dict[str, Any]]:
    for path in (
        STRUCTURAL_AUDIT_PATH,
        SUITABILITY_PREDICTIONS_PATH,
        STAGE78_UNIVERSE_PATH,
        STAGE78_ELIGIBILITY_PATH,
        STAGE78_PRODUCT_ATTRIBUTION_PATH,
        STAGE78_SUMMARY_PATH,
    ):
        _require(path)

    structural = _read_csv(STRUCTURAL_AUDIT_PATH)
    predictions = _read_csv(SUITABILITY_PREDICTIONS_PATH)
    universe = _read_csv(STAGE78_UNIVERSE_PATH)
    eligibility = _read_csv(STAGE78_ELIGIBILITY_PATH)
    product_attr = _read_csv(STAGE78_PRODUCT_ATTRIBUTION_PATH)
    stage78_summary = json.loads(STAGE78_SUMMARY_PATH.read_text(encoding="utf-8"))
    market_daily = _read_csv(MARKET_DAILY_PATH) if MARKET_DAILY_PATH.exists() else pd.DataFrame()

    structural_numeric = [
        "is_static_strategy_product",
        "mapping_coverage_ratio",
        "recently_active",
        "main_contract_count",
        "price_tick",
        "volume_multiple",
        "slippage",
        "margin_ratio",
        "notional_per_contract",
        "estimated_margin_per_contract",
        "metadata_ok",
        "recent_mapping_days",
        "recent_bar_coverage_ratio",
        "recent_nonzero_volume_ratio",
        "recent_median_volume",
        "recent_median_open_interest",
        "eligible",
        "market_trend_efficiency_60d_median",
        "market_trend_efficiency_120d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
        "market_volume_ratio_60d_median",
        "market_open_interest_change_60d_median",
        "structural_prefilter_kept",
    ]
    structural = _numeric(structural, structural_numeric)
    structural["log_recent_median_volume"] = np.log1p(structural["recent_median_volume"].clip(lower=0.0))
    structural["log_recent_median_open_interest"] = np.log1p(
        structural["recent_median_open_interest"].clip(lower=0.0)
    )

    score_source = structural[structural["eligible"].astype(int).eq(1)].copy()
    if score_source.empty:
        score_source = structural.copy()

    for column, high_is_good in [
        ("log_recent_median_volume", True),
        ("log_recent_median_open_interest", True),
        ("recent_bar_coverage_ratio", True),
        ("recent_nonzero_volume_ratio", True),
        ("market_trend_efficiency_60d_median", True),
        ("market_trend_efficiency_120d_median", True),
        ("market_realized_vol_60d_median", True),
        ("market_range_pct_mean_60d_median", True),
        ("market_volume_ratio_60d_median", True),
        ("estimated_margin_per_contract", False),
    ]:
        percentile = _rank_pct(score_source[column], high_is_good=high_is_good)
        structural = structural.merge(
            pd.DataFrame(
                {
                    "product_vt_symbol": score_source["product_vt_symbol"].to_numpy(),
                    f"{column}_pct": percentile.to_numpy(),
                }
            ),
            on="product_vt_symbol",
            how="left",
        )
        structural[f"{column}_pct"] = structural[f"{column}_pct"].fillna(0.0)

    structural["liquidity_score"] = (
        0.45 * structural["log_recent_median_volume_pct"]
        + 0.25 * structural["log_recent_median_open_interest_pct"]
        + 0.15 * structural["recent_bar_coverage_ratio_pct"]
        + 0.15 * structural["recent_nonzero_volume_ratio_pct"]
    )
    structural["trend_structure_score"] = (
        0.35 * structural["market_trend_efficiency_60d_median_pct"]
        + 0.20 * structural["market_trend_efficiency_120d_median_pct"]
        + 0.20 * structural["market_range_pct_mean_60d_median_pct"]
        + 0.15 * structural["market_realized_vol_60d_median_pct"]
        + 0.10 * structural["market_volume_ratio_60d_median_pct"]
    )
    structural["capital_friendliness_score"] = structural["estimated_margin_per_contract_pct"]
    structural["structure_score"] = (
        0.45 * structural["trend_structure_score"]
        + 0.35 * structural["liquidity_score"]
        + 0.20 * structural["capital_friendliness_score"]
    )
    structural["structure_score"] = _bounded_score(structural["structure_score"])

    prediction_summary = _build_prediction_summary(predictions)
    for column, high_is_good in [
        ("mean_ai_probability", True),
        ("median_simple_trend_score_pct", True),
        ("ai_top8_frequency_pct", True),
        ("future_60d_total_net_pnl", True),
        ("future_60d_positive_rate_pct", True),
        ("future_60d_top_half_rate_pct", True),
        ("future_60d_mean_rank_centered", True),
    ]:
        prediction_summary[f"{column}_pct"] = _rank_pct(prediction_summary[column], high_is_good=high_is_good)

    prediction_summary["mechanism_score"] = (
        0.50 * prediction_summary["mean_ai_probability_pct"]
        + 0.30 * prediction_summary["median_simple_trend_score_pct_pct"]
        + 0.20 * prediction_summary["ai_top8_frequency_pct_pct"]
    )
    prediction_summary["oos_evidence_score"] = (
        0.25 * prediction_summary["future_60d_total_net_pnl_pct"]
        + 0.25 * prediction_summary["future_60d_positive_rate_pct_pct"]
        + 0.25 * prediction_summary["future_60d_top_half_rate_pct_pct"]
        + 0.25 * prediction_summary["future_60d_mean_rank_centered_pct"]
    )

    universe_flags = universe[["product_vt_symbol", "is_static_strategy_product"]].copy()
    universe_flags["is_stage78_universe"] = True
    universe_flags["is_manual_static18"] = universe_flags["is_static_strategy_product"].astype(int).eq(1)
    universe_flags["is_fu_satellite"] = universe_flags["product_vt_symbol"].eq("fu.SHFE")

    eligibility_summary = _build_ai_eligibility_summary(eligibility)
    attr = product_attr.rename(
        columns={
            "full_net_pnl": "stage78_full_net_pnl",
            "trade_count": "stage78_trade_count",
            "slippage": "stage78_slippage",
            "active_days": "stage78_active_days",
        }
    )
    attr = _numeric(attr, ["stage78_full_net_pnl", "stage78_trade_count", "stage78_slippage", "stage78_active_days", "pnl_rank"])
    attr["stage78_pnl_per_trade"] = np.where(
        attr["stage78_trade_count"] > 0,
        attr["stage78_full_net_pnl"] / attr["stage78_trade_count"],
        0.0,
    )

    corr_features = _calc_correlation_features(market_daily, set(universe["product_vt_symbol"]))

    scores = (
        structural.merge(prediction_summary, on="product_vt_symbol", how="left")
        .merge(universe_flags.drop(columns=["is_static_strategy_product"], errors="ignore"), on="product_vt_symbol", how="left")
        .merge(eligibility_summary, on="product_vt_symbol", how="left")
        .merge(attr, on="product_vt_symbol", how="left")
        .merge(corr_features, on="product_vt_symbol", how="left")
    )
    fill_false = ["is_stage78_universe", "is_manual_static18", "is_fu_satellite"]
    for column in fill_false:
        scores[column] = scores[column].map(lambda value: False if pd.isna(value) else bool(value))
    scores["is_stage78_ai_selected"] = pd.to_numeric(
        scores.get("stage78_ai_selected_count", 0.0), errors="coerce"
    ).fillna(0.0) > 0

    fill_numeric = [
        "wf_eval_count",
        "mean_ai_probability",
        "median_ai_probability",
        "median_simple_trend_score_pct",
        "ai_top5_frequency_pct",
        "ai_top8_frequency_pct",
        "future_60d_total_net_pnl",
        "future_60d_mean_net_pnl",
        "future_60d_positive_rate_pct",
        "future_60d_top_half_rate_pct",
        "future_60d_mean_rank_centered",
        "mechanism_score",
        "oos_evidence_score",
        "stage78_ai_selected_count",
        "stage78_ai_eval_month_count",
        "stage78_ai_selected_frequency_pct",
        "stage78_ai_mean_rank",
        "stage78_ai_best_rank",
        "stage78_ai_mean_score",
        "stage78_full_net_pnl",
        "stage78_trade_count",
        "stage78_slippage",
        "stage78_active_days",
        "stage78_pnl_per_trade",
        "pnl_rank",
        "avg_abs_corr_to_stage78",
        "avg_abs_corr_to_all",
        "max_abs_corr_to_stage78",
    ]
    _numeric(scores, fill_numeric)

    scores["diversification_score"] = (1.0 - scores["avg_abs_corr_to_stage78"].clip(0.0, 1.0)).fillna(0.0)
    scores["audit_score"] = (
        0.40 * scores["structure_score"]
        + 0.25 * scores["mechanism_score"]
        + 0.20 * scores["oos_evidence_score"]
        + 0.15 * scores["diversification_score"]
    )
    scores["audit_score"] = _bounded_score(scores["audit_score"])

    core_condition = (
        scores["structure_score"].ge(0.67)
        & scores["mechanism_score"].ge(0.60)
        & scores["oos_evidence_score"].ge(0.55)
        & scores["future_60d_total_net_pnl"].ge(0.0)
        & scores["future_60d_top_half_rate_pct"].ge(50.0)
    )
    satellite_condition = (
        scores["structure_score"].ge(0.60)
        & (scores["mechanism_score"].ge(0.55) | scores["oos_evidence_score"].ge(0.55))
        & (
            scores["future_60d_total_net_pnl"].ge(0.0)
            | scores["stage78_full_net_pnl"].gt(0.0)
            | scores["is_fu_satellite"]
        )
    )
    watchlist_condition = (
        scores["structure_score"].ge(0.50)
        | scores["mechanism_score"].ge(0.50)
        | scores["oos_evidence_score"].ge(0.50)
    )
    conditions = [
        (scores["eligible"].astype(int).ne(1)) | (scores["structural_prefilter_kept"].astype(int).ne(1)),
        core_condition,
        satellite_condition,
        watchlist_condition,
    ]
    choices = ["reject", "core_candidate", "satellite_candidate", "watchlist"]
    scores["fit_layer"] = np.select(conditions, choices, default="reject")
    scores["origin_group"] = scores.apply(_origin_group, axis=1)
    scores["classification_reason"] = scores.apply(_classification_reason, axis=1)
    scores["is_formal_rule"] = False
    scores["promotion_status"] = np.where(
        scores["fit_layer"].isin(["core_candidate", "satellite_candidate"]),
        "shadow_candidate_only",
        "audit_only",
    )
    scores["audit_rank"] = scores["audit_score"].rank(ascending=False, method="first").astype(int)
    scores = scores.sort_values(["audit_rank", "product_vt_symbol"]).reset_index(drop=True)

    metadata = {
        "stage78_summary": stage78_summary,
        "input_rows": {
            "structural": int(len(structural)),
            "predictions": int(len(predictions)),
            "market_daily": int(len(market_daily)),
            "universe": int(len(universe)),
            "eligibility": int(len(eligibility)),
            "product_attr": int(len(product_attr)),
        },
        "score_weights": {
            "audit_score": {
                "structure_score": 0.40,
                "mechanism_score": 0.25,
                "oos_evidence_score": 0.20,
                "diversification_score": 0.15,
            },
            "structure_score": {
                "trend_structure_score": 0.45,
                "liquidity_score": 0.35,
                "capital_friendliness_score": 0.20,
            },
        },
    }
    return scores, metadata


def _build_summaries(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    layer_summary = (
        scores.groupby("fit_layer", as_index=False)
        .agg(
            product_count=("product_vt_symbol", "count"),
            manual_static18_count=("is_manual_static18", "sum"),
            fu_satellite_count=("is_fu_satellite", "sum"),
            stage78_ai_selected_count=("is_stage78_ai_selected", "sum"),
            mean_audit_score=("audit_score", "mean"),
            mean_structure_score=("structure_score", "mean"),
            mean_mechanism_score=("mechanism_score", "mean"),
            mean_oos_evidence_score=("oos_evidence_score", "mean"),
            mean_diversification_score=("diversification_score", "mean"),
            future_60d_total_net_pnl=("future_60d_total_net_pnl", "sum"),
            stage78_full_net_pnl=("stage78_full_net_pnl", "sum"),
            mean_avg_abs_corr_to_stage78=("avg_abs_corr_to_stage78", "mean"),
        )
        .sort_values("mean_audit_score", ascending=False)
        .reset_index(drop=True)
    )
    origin_summary = (
        scores.groupby("origin_group", as_index=False)
        .agg(
            product_count=("product_vt_symbol", "count"),
            core_count=("fit_layer", lambda s: int((s == "core_candidate").sum())),
            satellite_count=("fit_layer", lambda s: int((s == "satellite_candidate").sum())),
            watchlist_count=("fit_layer", lambda s: int((s == "watchlist").sum())),
            reject_count=("fit_layer", lambda s: int((s == "reject").sum())),
            mean_audit_score=("audit_score", "mean"),
            mean_structure_score=("structure_score", "mean"),
            mean_mechanism_score=("mechanism_score", "mean"),
            mean_oos_evidence_score=("oos_evidence_score", "mean"),
            future_60d_total_net_pnl=("future_60d_total_net_pnl", "sum"),
            stage78_full_net_pnl=("stage78_full_net_pnl", "sum"),
        )
        .sort_values("mean_audit_score", ascending=False)
        .reset_index(drop=True)
    )
    top_candidates = scores[
        scores["fit_layer"].isin(["core_candidate", "satellite_candidate", "watchlist"])
    ].copy()
    top_candidates = top_candidates.sort_values(["fit_layer", "audit_score"], ascending=[True, False]).reset_index(
        drop=True
    )
    return layer_summary, origin_summary, top_candidates


def _build_summary_payload(
    scores: pd.DataFrame,
    layer_summary: pd.DataFrame,
    origin_summary: pd.DataFrame,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    stage78_full = metadata["stage78_summary"]["reference_metrics"]["full_2020_2026"]
    manual = scores[scores["is_manual_static18"]].copy()
    non_manual_eligible = scores[(~scores["is_stage78_universe"]) & scores["eligible"].astype(int).eq(1)].copy()
    core = scores[scores["fit_layer"].eq("core_candidate")].copy()
    satellite = scores[scores["fit_layer"].eq("satellite_candidate")].copy()
    return {
        "model_tag": MODEL_TAG,
        "stage78_reference": stage78_full,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "anti_overfit_boundary": (
            "This is a full-market audit only. It does not create a new trading pool, "
            "does not use historical top-N as a formal rule, and does not change Stage78."
        ),
        "input_rows": metadata["input_rows"],
        "score_weights": metadata["score_weights"],
        "total_products": int(len(scores)),
        "eligible_products": int(scores["eligible"].astype(int).sum()),
        "core_candidate_count": int((scores["fit_layer"] == "core_candidate").sum()),
        "satellite_candidate_count": int((scores["fit_layer"] == "satellite_candidate").sum()),
        "watchlist_count": int((scores["fit_layer"] == "watchlist").sum()),
        "reject_count": int((scores["fit_layer"] == "reject").sum()),
        "manual_static18_count": int(len(manual)),
        "manual_static18_core_or_satellite_count": int(manual["fit_layer"].isin(["core_candidate", "satellite_candidate"]).sum()),
        "non_manual_eligible_count": int(len(non_manual_eligible)),
        "non_manual_core_or_satellite_count": int(
            non_manual_eligible["fit_layer"].isin(["core_candidate", "satellite_candidate"]).sum()
        ),
        "core_candidates": core["product_vt_symbol"].head(20).tolist(),
        "satellite_candidates": satellite["product_vt_symbol"].head(20).tolist(),
        "layer_summary": layer_summary.to_dict(orient="records"),
        "origin_summary": origin_summary.to_dict(orient="records"),
    }


def _write_report(
    scores: pd.DataFrame,
    layer_summary: pd.DataFrame,
    origin_summary: pd.DataFrame,
    top_candidates: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    stage78 = summary["stage78_reference"]
    manual = scores[scores["is_manual_static18"]].sort_values("audit_score", ascending=False)
    non_manual = scores[(~scores["is_stage78_universe"]) & scores["eligible"].astype(int).eq(1)].sort_values(
        "audit_score", ascending=False
    )
    fu = scores[scores["product_vt_symbol"].eq("fu.SHFE")]
    layer_cols = [
        "fit_layer",
        "product_count",
        "manual_static18_count",
        "fu_satellite_count",
        "stage78_ai_selected_count",
        "mean_audit_score",
        "mean_structure_score",
        "mean_mechanism_score",
        "mean_oos_evidence_score",
        "future_60d_total_net_pnl",
        "stage78_full_net_pnl",
    ]
    product_cols = [
        "audit_rank",
        "product_vt_symbol",
        "fit_layer",
        "origin_group",
        "audit_score",
        "structure_score",
        "mechanism_score",
        "oos_evidence_score",
        "diversification_score",
        "future_60d_total_net_pnl",
        "future_60d_positive_rate_pct",
        "future_60d_top_half_rate_pct",
        "stage78_full_net_pnl",
        "stage78_ai_selected_frequency_pct",
        "avg_abs_corr_to_stage78",
        "classification_reason",
    ]
    report = f"""# Stage140 全市场品种适配度审计

## 结论
- 本阶段不是正式策略版本，不改 Stage78，不触发 `skills/version-ab-experiment/SKILL.md`；原因是它只做全市场品种适配度审计，没有提出可接入正式版的交易规则。
- 过拟合判断：否。评分框架把先验结构、AI机制分、样本外证据和相关性分开，历史收益只占证据的一部分，没有用历史收益 TopN 直接反推交易池。
- 是否有价值继续：是。它能回答“肉眼18品种是否有结构优势、全市场是否存在可观察候选”，比继续拧阈值更接近策略底层资产池问题。

## Stage78 基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 分层统计
{_to_markdown_table(layer_summary, layer_cols, max_rows=20)}

## 来源组对比
{_to_markdown_table(origin_summary, max_rows=20)}

## 候选清单
{_to_markdown_table(top_candidates.sort_values("audit_score", ascending=False), product_cols, max_rows=25)}

## 原始18品种审计
{_to_markdown_table(manual, product_cols, max_rows=25)}

## 非Stage78全市场候选
{_to_markdown_table(non_manual, product_cols, max_rows=25)}

## fu 单独定位
{_to_markdown_table(fu, product_cols, max_rows=5)}

## 方法边界
- 结构分只看流动性、持仓、趋势效率、波动/振幅、资金友好度，不看最终收益。
- AI机制分来自已有 walk-forward 适配度模型的概率和入选频率，用来模拟“结构化经验放大器”，不是下单信号。
- 样本外证据分使用每个评估点之后60日的历史标签，只作为审计证据，不允许直接变成 TopN 交易池。
- 相关性分只用于惩罚和 Stage78 过度同质化的品种，避免全池看似多品种、实质押同一宏观因子。

## 后续规划
- 如果候选集中出现非Stage78品种，并且不是单一品种孤例，下一步只做 Stage141 影子组合观察，不直接替换 Stage78。
- 如果候选主要仍集中在原始18品种，说明肉眼经验本身有价值，后续重点应转向 Stage78 准实盘复盘、执行成本和池子更新节奏，而不是扩大品种池。
- 禁止把本表中单个品种的高历史贡献直接写成特例规则。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    scores, metadata = _build_product_scores()
    layer_summary, origin_summary, top_candidates = _build_summaries(scores)
    summary = _build_summary_payload(scores, layer_summary, origin_summary, metadata)

    scores.to_csv(PRODUCT_SCORE_PATH, index=False, encoding="utf-8-sig")
    layer_summary.to_csv(LAYER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    origin_summary.to_csv(ORIGIN_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_candidates.to_csv(TOP_CANDIDATE_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(scores, layer_summary, origin_summary, top_candidates, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote: {PRODUCT_SCORE_PATH}")
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()

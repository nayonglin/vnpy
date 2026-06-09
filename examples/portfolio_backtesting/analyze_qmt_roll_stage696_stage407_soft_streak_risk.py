from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage692_official_stage372_jd_top9_maxpos5 as s692
from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import (
    PREDICTIONS_OUTPUT_PATH as FULL_MARKET_AI_PREDICTIONS_PATH,
)
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, OFFICIAL_LIVE_PROFILE_NAME
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_entry_risk_diagnostics_df


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage696_stage407_soft_streak_risk_v1"
OUTPUT_PREFIX = "qmt_roll_stage696_stage407_soft_streak_risk"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
OFFICIAL_SOFT_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_soft_streak_1_1_05_025"
STAGE407_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5"
TARGET_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_soft_streak_1_1_05_025"
)

JD_PRODUCT = "jd.DCE"
AI_TOP_N = 9
AI_STRATEGY = "stage696_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage696_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage696_official_ai_pre_full_market_coverage"
SOFT_STREAK_MULTIPLIERS = "1.0,1.0,0.5,0.25"
BASE_STREAK_MULTIPLIERS = "1.0,1.0,1.0,0.1"
WINDOW_START = "2025-04-16"
WINDOW_END = "2025-07-25"

GENERATED_DIR = OUTPUT_DIR / "stage696_generated_inputs"
UNIVERSE_PLUS_JD_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_original_ai_plus_jd_rerank_top9_eligibility_{MODEL_TAG}.csv"
MISSING_PREDICTION_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_missing_prediction_candidates_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv"
PRODUCT_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_RISK_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_summary_{MODEL_TAG}.csv"
WINDOW_GROWTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_growth_{MODEL_TAG}.csv"
WINDOW_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_product_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_only_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s692._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s692._md_table(frame, max_rows=max_rows)


def _product_from_symbol(symbol: Any) -> str:
    text = str(symbol or "")
    first = text.split(".", 1)[0]
    product = ""
    for char in first:
        if char.isalpha():
            product += char
        else:
            break
    return product.lower()


def _write_plus_jd_universe(base_symbols: list[str]) -> dict[str, Any]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    plus_symbols = sorted(set(base_symbols) | {JD_PRODUCT})
    rows = []
    for symbol in plus_symbols:
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage696_original_ai_plus_jd_soft_streak_ab",
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PLUS_JD_PATH, index=False, encoding="utf-8-sig")
    return {
        "base_symbols": sorted(base_symbols),
        "plus_symbols": plus_symbols,
        "effective_new_products": sorted({JD_PRODUCT} - set(base_symbols)),
        "already_in_base": sorted(set(base_symbols) & {JD_PRODUCT}),
    }


def _official_pre_full_market_rows(first_full_market_eval: str) -> pd.DataFrame:
    official = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(official.columns)
    if missing:
        raise ValueError(f"official eligibility missing columns {sorted(missing)}")
    official["eval_date"] = pd.to_datetime(official["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    official = official[official["eval_date"].astype(str) < first_full_market_eval].copy()
    if official.empty:
        return official
    source_strategy = str(official["strategy"].dropna().astype(str).iloc[0])
    official = official[official["strategy"].astype(str).eq(source_strategy)].copy()
    official["strategy"] = AI_STRATEGY
    official["score_type"] = AI_PRE_COVERAGE_SCORE_TYPE
    for column in ["score", "score_rank", "top_n"]:
        official[column] = pd.to_numeric(official[column], errors="coerce").fillna(0.0)
    official["top_n"] = official.groupby("eval_date")["product_vt_symbol"].transform("count")
    return official[list(required)].copy()


def _write_original_ai_plus_jd_rerank_top9_eligibility(symbols: list[str]) -> pd.DataFrame:
    official = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(official.columns)
    if missing:
        raise ValueError(f"official eligibility missing columns {sorted(missing)}")

    official["eval_date"] = pd.to_datetime(official["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    source_strategy = str(official["strategy"].dropna().astype(str).iloc[0])
    official = official[official["strategy"].astype(str).eq(source_strategy)].copy()
    official = official[official["product_vt_symbol"].astype(str).isin(set(symbols))].copy()

    predictions = pd.read_csv(
        FULL_MARKET_AI_PREDICTIONS_PATH,
        usecols=["eval_date", "product_vt_symbol", PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN],
    )
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    predictions["product_vt_symbol"] = predictions["product_vt_symbol"].astype(str)
    predictions = predictions[predictions["product_vt_symbol"].isin(set(symbols))].copy()
    if predictions.empty:
        raise RuntimeError("no full-market AI prediction rows for original-ai-plus-jd universe")

    first_full_market_eval = str(predictions["eval_date"].min())
    pre_rows = _official_pre_full_market_rows(first_full_market_eval)
    pred_by_date = {date: frame.copy() for date, frame in predictions.groupby("eval_date", sort=False)}

    rows: list[dict[str, Any]] = []
    missing_prediction_rows: list[dict[str, Any]] = []
    for eval_date, official_group in official.groupby("eval_date", sort=True):
        eval_date = str(eval_date)
        if eval_date < first_full_market_eval:
            continue
        candidates = set(official_group["product_vt_symbol"].astype(str)) | {JD_PRODUCT}
        pred_group = pred_by_date.get(eval_date, pd.DataFrame(columns=predictions.columns))
        pred_group = pred_group[pred_group["product_vt_symbol"].isin(candidates)].copy()
        missing_candidates = sorted(candidates - set(pred_group["product_vt_symbol"].astype(str)))
        if missing_candidates:
            missing_prediction_rows.append(
                {
                    "eval_date": eval_date,
                    "missing_candidates": ",".join(missing_candidates),
                    "missing_count": len(missing_candidates),
                }
            )
        if pred_group.empty:
            continue
        ranked = pred_group.sort_values(
            [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        ranked["score_rank"] = range(1, len(ranked) + 1)
        selected = ranked.head(AI_TOP_N).copy()
        for row in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": AI_STRATEGY,
                    "score_type": AI_SCORE_TYPE,
                    "eval_date": eval_date,
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, PROBABILITY_COLUMN)),
                    "score_rank": int(getattr(row, "score_rank")),
                    "top_n": AI_TOP_N,
                }
            )

    reranked = pd.DataFrame(rows)
    if reranked.empty:
        raise RuntimeError("AI rerank produced no eligibility rows")
    eligibility = pd.concat([pre_rows, reranked], ignore_index=True, sort=False)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    eligibility.reset_index(drop=True, inplace=True)
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    if missing_prediction_rows:
        pd.DataFrame(missing_prediction_rows).to_csv(MISSING_PREDICTION_PATH, index=False, encoding="utf-8-sig")
    return eligibility


def _ai_audit(eligibility: pd.DataFrame) -> pd.DataFrame:
    data = eligibility.copy()
    data["is_jd"] = data["product_vt_symbol"].astype(str).eq(JD_PRODUCT).astype(int)
    rows: list[dict[str, Any]] = []
    for eval_date, group in data.groupby("eval_date", sort=True):
        jd = group[group["is_jd"].eq(1)]
        rows.append(
            {
                "eval_date": str(eval_date),
                "selected_count": int(group["product_vt_symbol"].nunique()),
                "jd_selected": int(not jd.empty),
                "jd_rank": int(pd.to_numeric(jd["score_rank"], errors="coerce").iloc[0]) if not jd.empty else 0,
                "jd_score": float(pd.to_numeric(jd["score"], errors="coerce").iloc[0]) if not jd.empty else 0.0,
                "score_type": str(group["score_type"].astype(str).iloc[0]) if not group.empty else "",
                "selected_products": ",".join(group.sort_values("score_rank")["product_vt_symbol"].astype(str).tolist()),
            }
        )
    return pd.DataFrame(rows)


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = s692.s666._official_symbols()
    universe = _write_plus_jd_universe(base_symbols)
    eligibility = _write_original_ai_plus_jd_rerank_top9_eligibility(universe["plus_symbols"])
    base_metadata = s692.s666.build_contract_metadata(supported_symbols=universe["base_symbols"])
    plus_metadata = s692.s666.build_contract_metadata(supported_symbols=universe["plus_symbols"])
    ai_audit = _ai_audit(eligibility)
    ai_audit.to_csv(AI_AUDIT_PATH, index=False, encoding="utf-8-sig")
    return {
        **universe,
        "base_metadata": base_metadata,
        "plus_metadata": plus_metadata,
        "base_product_count": len(universe["base_symbols"]),
        "plus_product_count": len(universe["plus_symbols"]),
        "ai_eval_date_min": str(eligibility["eval_date"].min()),
        "ai_eval_date_max": str(eligibility["eval_date"].max()),
        "ai_eval_dates": int(eligibility["eval_date"].nunique()),
        "ai_audit": ai_audit,
        "universe_path": str(UNIVERSE_PLUS_JD_PATH),
        "eligibility_path": str(ELIGIBILITY_PATH),
    }


def _official_spec(identity_map: str) -> s692.s653.ForcedVariant:
    spec = s692._official_spec(identity_map)
    overrides = {**spec.overrides, "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)}
    return replace(spec, overrides=overrides)


def _official_soft_spec(identity_map: str) -> s692.s653.ForcedVariant:
    base = _official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=OFFICIAL_SOFT_VARIANT,
        label="Stage409 official Stage372 soft streak risk",
        note=(
            "Official Stage372 unchanged except streak_risk_multipliers is softened from "
            f"{BASE_STREAK_MULTIPLIERS} to {SOFT_STREAK_MULTIPLIERS}."
        ),
    )
    overrides = {**base.overrides, "streak_risk_multipliers": SOFT_STREAK_MULTIPLIERS}
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_soft_streak_risk")


def _stage407_spec(identity_map: str, *, soft_streak: bool) -> s692.s653.ForcedVariant:
    base = _official_spec(identity_map)
    variant = TARGET_VARIANT if soft_streak else STAGE407_VARIANT
    label = "Stage409 Stage407 plus jd AI rerank top9 maxpos5 soft streak" if soft_streak else "Stage407 baseline rerun"
    note = (
        "Stage409 C: Stage407 original AI pool plus jd AI rerank top9 maxpos5, "
        f"but streak_risk_multipliers is softened to {SOFT_STREAK_MULTIPLIERS}."
        if soft_streak
        else "Stage407 B rerun: original AI pool plus jd AI rerank top9 maxpos5 with the original hard 0.1 loss-streak floor."
    )
    capital = replace(base.capital, variant=variant, label=label, max_concurrent_positions=5, note=note)
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(UNIVERSE_PLUS_JD_PATH),
        "max_concurrent_positions": 5,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
        "ai_product_pool_strategy": AI_STRATEGY,
    }
    if soft_streak:
        overrides["streak_risk_multipliers"] = SOFT_STREAK_MULTIPLIERS
    else:
        overrides["streak_risk_multipliers"] = BASE_STREAK_MULTIPLIERS
    profile = "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5_soft_streak" if soft_streak else "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5"
    return replace(base, capital=capital, overrides=overrides, profile=profile)


def _run_variant_with_diagnostics(
    spec: s692.s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s692.s653.s517.assert_stage196_database_sentinels()
    s692.s653.s517.s506._patch_stage506_raw_roots()
    c3_overrides = s692.s513._c3_overrides(s692.s653.s517.START_DT)
    preload_start = max(s692.s653.s517.PRELOAD_START_DT, s692.s653.s517.START_DT - timedelta(days=365))
    _, open_map = s692.s653.s517.s506.s501._seed_proxy_maps()
    engine = s692.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s692.s653.s517.Interval.DAILY,
        start=preload_start,
        end=s692.s653.s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s692.s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s692.s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.capital.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= s692.s653.s517.START_DT.date()) & (daily.index <= s692.s653.s517.END_DT.date())
    ].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = spec.capital.c3_capital + daily["net_pnl"].cumsum()
    daily["variant"] = spec.capital.variant
    daily["combo_variant"] = spec.capital.variant
    daily["label"] = spec.capital.label
    daily["risk_multiplier"] = spec.capital.risk_multiplier
    daily["note"] = spec.capital.note

    strategy = getattr(engine, "strategy", None)
    daily["forced_margin_deleverage_count"] = int(getattr(strategy, "forced_margin_deleverage_count", 0) or 0)
    daily["forced_margin_deleverage_closed_volume"] = int(
        getattr(strategy, "forced_margin_deleverage_closed_volume", 0) or 0
    )
    daily["forced_margin_deleverage_ratio"] = float(getattr(strategy, "forced_margin_deleverage_ratio", 0.0) or 0.0)
    daily["forced_margin_deleverage_max_observed_ratio"] = float(
        getattr(strategy, "forced_margin_deleverage_max_observed_ratio", 0.0) or 0.0
    )

    positions = s692.s653.s517.build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.capital.variant}")
    positions["variant"] = spec.capital.variant
    positions["combo_variant"] = spec.capital.variant
    positions["label"] = spec.capital.label
    positions["risk_multiplier"] = spec.capital.risk_multiplier

    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = spec.capital.variant
        usage["label"] = spec.capital.label
        usage["risk_multiplier"] = spec.capital.risk_multiplier

    candidates = build_entry_candidate_snapshots_df(engine)
    if not candidates.empty:
        candidates["variant"] = spec.capital.variant
        candidates["label"] = spec.capital.label

    entry_risk = build_entry_risk_diagnostics_df(engine)
    if not entry_risk.empty:
        entry_risk["variant"] = spec.capital.variant
        entry_risk["label"] = spec.capital.label

    forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile

    c3_margin_daily, product_margin = s692.s513._position_margin(positions, metadata)
    combined = s692.s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, positions, product_margin, usage, candidates, entry_risk, forced_events


def _annual_monthly(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    return s692._annual_monthly(daily)


def _product_summary(positions: pd.DataFrame) -> pd.DataFrame:
    return s692._product_summary(positions)


def _product_delta(product: pd.DataFrame) -> pd.DataFrame:
    if product.empty:
        return pd.DataFrame()
    variants = [BASE_VARIANT, OFFICIAL_SOFT_VARIANT, STAGE407_VARIANT, TARGET_VARIANT]
    frames = {
        variant: product[product["variant"].eq(variant)].set_index("product")
        for variant in variants
    }
    products = sorted(set().union(*(set(frame.index) for frame in frames.values())))
    rows: list[dict[str, Any]] = []
    for product_name in products:
        row = {"product": product_name}
        for variant, frame in frames.items():
            row[f"{variant}_net_pnl"] = float(frame.loc[product_name, "net_pnl"]) if product_name in frame.index else 0.0
            row[f"{variant}_trade_count"] = float(frame.loc[product_name, "trade_count"]) if product_name in frame.index else 0.0
        row["delta_target_vs_stage407"] = row[f"{TARGET_VARIANT}_net_pnl"] - row[f"{STAGE407_VARIANT}_net_pnl"]
        row["delta_target_vs_official"] = row[f"{TARGET_VARIANT}_net_pnl"] - row[f"{BASE_VARIANT}_net_pnl"]
        row["delta_official_soft_vs_official"] = row[f"{OFFICIAL_SOFT_VARIANT}_net_pnl"] - row[f"{BASE_VARIANT}_net_pnl"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("delta_target_vs_stage407", ascending=False)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("official_soft_vs_official", BASE_VARIANT, OFFICIAL_SOFT_VARIANT),
        ("stage407_soft_vs_stage407", STAGE407_VARIANT, TARGET_VARIANT),
        ("stage407_vs_official", BASE_VARIANT, STAGE407_VARIANT),
        ("stage407_soft_vs_official", BASE_VARIANT, TARGET_VARIANT),
    ]
    fields = [
        ("end_equity", "end_equity"),
        ("total_return_pct", "return_pct"),
        ("max_dd_pct", "max_dd_pct"),
        ("sharpe", "sharpe"),
        ("total_slippage", "slippage"),
        ("total_trade_count", "trade_count"),
        ("nonzero_daily_win_rate_pct", "win_rate_pct"),
        ("max_broker10_margin_to_equity_pct", "max_margin_pct"),
        ("p95_broker10_margin_to_equity_pct", "p95_margin_pct"),
        ("forced_margin_deleverage_count", "forced_count"),
        ("forced_margin_deleverage_closed_volume", "forced_volume"),
    ]
    by_variant = {variant: frame.iloc[0].to_dict() for variant, frame in summary.groupby("variant", sort=False)}
    cost_by_variant = {variant: frame.set_index("cost_multiplier") for variant, frame in cost.groupby("variant", sort=False)}
    rows: list[dict[str, Any]] = []
    for compare_name, reference_variant, candidate_variant in pairs:
        if reference_variant not in by_variant or candidate_variant not in by_variant:
            continue
        ref = by_variant[reference_variant]
        cand = by_variant[candidate_variant]
        for source, metric in fields:
            reference_value = float(ref.get(source, 0.0) or 0.0)
            candidate_value = float(cand.get(source, 0.0) or 0.0)
            rows.append(
                {
                    "compare_name": compare_name,
                    "metric": metric,
                    "reference_variant": reference_variant,
                    "candidate_variant": candidate_variant,
                    "reference_value": reference_value,
                    "candidate_value": candidate_value,
                    "delta": candidate_value - reference_value,
                }
            )
        ref_cost = cost_by_variant.get(reference_variant, pd.DataFrame())
        cand_cost = cost_by_variant.get(candidate_variant, pd.DataFrame())
        for multiplier in (2.0, 3.0):
            if multiplier in ref_cost.index and multiplier in cand_cost.index:
                for metric, column in (("max_dd_pct", "max_dd_pct"), ("end_equity", "end_equity")):
                    reference_value = float(ref_cost.loc[multiplier, column])
                    candidate_value = float(cand_cost.loc[multiplier, column])
                    rows.append(
                        {
                            "compare_name": compare_name,
                            "metric": f"{multiplier}x_cost_{metric}",
                            "reference_variant": reference_variant,
                            "candidate_variant": candidate_variant,
                            "reference_value": reference_value,
                            "candidate_value": candidate_value,
                            "delta": candidate_value - reference_value,
                        }
                    )
    return pd.DataFrame(rows)


def _window_growth(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce").fillna(0.0)
    start = pd.Timestamp(WINDOW_START)
    end = pd.Timestamp(WINDOW_END)
    rows: list[dict[str, Any]] = []
    for variant, group in data.groupby("variant", sort=False):
        group = group.sort_values("date")
        window = group[(group["date"] >= start) & (group["date"] <= end)].copy()
        if window.empty:
            continue
        rows.append(
            {
                "variant": variant,
                "window_start": WINDOW_START,
                "window_end": WINDOW_END,
                "start_equity": float(window["account_equity"].iloc[0]),
                "end_equity": float(window["account_equity"].iloc[-1]),
                "growth": float(window["account_equity"].iloc[-1] - window["account_equity"].iloc[0]),
                "return_pct": float((window["account_equity"].iloc[-1] / window["account_equity"].iloc[0] - 1.0) * 100.0),
                "trade_count": float(pd.to_numeric(window.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "slippage": float(pd.to_numeric(window.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _window_product(positions: pd.DataFrame) -> pd.DataFrame:
    data = positions.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data[(data["date"] >= pd.Timestamp(WINDOW_START)) & (data["date"] <= pd.Timestamp(WINDOW_END))].copy()
    if data.empty:
        return pd.DataFrame()
    data["product"] = data["vt_symbol"].map(_product_from_symbol)
    for column in ["net_pnl", "slippage", "trade_count"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    rows = []
    for (variant, product), group in data.groupby(["variant", "product"], sort=True):
        rows.append(
            {
                "variant": variant,
                "product": product,
                "window_net_pnl": float(group["net_pnl"].sum()),
                "window_slippage": float(group["slippage"].sum()),
                "window_trade_count": float(group["trade_count"].sum()),
            }
        )
    frame = pd.DataFrame(rows)
    base = frame[frame["variant"].eq(STAGE407_VARIANT)].set_index("product")
    target = frame[frame["variant"].eq(TARGET_VARIANT)].set_index("product")
    products = sorted(set(base.index) | set(target.index))
    delta_rows = []
    for product in products:
        base_pnl = float(base.loc[product, "window_net_pnl"]) if product in base.index else 0.0
        target_pnl = float(target.loc[product, "window_net_pnl"]) if product in target.index else 0.0
        delta_rows.append(
            {
                "product": product,
                "stage407_window_net_pnl": base_pnl,
                "soft_streak_window_net_pnl": target_pnl,
                "delta_soft_vs_stage407": target_pnl - base_pnl,
            }
        )
    delta = pd.DataFrame(delta_rows).sort_values("delta_soft_vs_stage407", ascending=False)
    return delta


def _entry_risk_summary(candidates: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not candidates.empty:
        cand = candidates.copy()
        cand["date"] = pd.to_datetime(cand["date"], errors="coerce").dt.normalize()
        for column in [
            "selected_volume",
            "contracts_by_risk",
            "contracts_by_margin",
            "target_risk_amount",
            "estimated_equity",
            "loss_streak",
            "is_opened",
        ]:
            cand[column] = pd.to_numeric(cand.get(column, 0.0), errors="coerce").fillna(0.0)
        cand["scope"] = "all_candidates"
        frames.append(cand)
        cand_window = cand[(cand["date"] >= pd.Timestamp(WINDOW_START)) & (cand["date"] <= pd.Timestamp(WINDOW_END))].copy()
        cand_window["scope"] = "window_candidates"
        frames.append(cand_window)
    if not entry_risk.empty:
        risk = entry_risk.copy()
        risk["date"] = pd.to_datetime(risk["date"], errors="coerce").dt.normalize()
        for column in [
            "selected_volume",
            "contracts_by_risk",
            "contracts_by_margin",
            "target_risk_amount",
            "actual_risk_amount",
            "estimated_equity",
            "loss_streak",
        ]:
            risk[column] = pd.to_numeric(risk.get(column, 0.0), errors="coerce").fillna(0.0)
        risk["candidate_status"] = "opened"
        risk["is_opened"] = 1
        risk["scope"] = "opened_entries"
        frames.append(risk)
        risk_window = risk[(risk["date"] >= pd.Timestamp(WINDOW_START)) & (risk["date"] <= pd.Timestamp(WINDOW_END))].copy()
        risk_window["scope"] = "window_opened_entries"
        frames.append(risk_window)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True, sort=False)
    rows: list[dict[str, Any]] = []
    for (variant, scope), group in data.groupby(["variant", "scope"], sort=True):
        zero_volume = group[group["selected_volume"].le(0)]
        risk_zero = zero_volume[
            zero_volume["contracts_by_risk"].le(0) & zero_volume["contracts_by_margin"].gt(0)
        ]
        loss_floor = group[group["loss_streak"].ge(3)]
        rows.append(
            {
                "variant": variant,
                "scope": scope,
                "rows": int(len(group)),
                "opened_rows": int(pd.to_numeric(group.get("is_opened", 0), errors="coerce").fillna(0.0).sum()),
                "zero_volume_rows": int(len(zero_volume)),
                "risk_zero_margin_positive_rows": int(len(risk_zero)),
                "loss_streak_ge3_rows": int(len(loss_floor)),
                "median_loss_streak": float(group["loss_streak"].median()) if not group.empty else 0.0,
                "median_target_risk_amount": float(group["target_risk_amount"].median()) if not group.empty else 0.0,
                "median_contracts_by_risk": float(group["contracts_by_risk"].median()) if not group.empty else 0.0,
                "median_contracts_by_margin": float(group["contracts_by_margin"].median()) if not group.empty else 0.0,
                "median_selected_volume": float(group["selected_volume"].median()) if not group.empty else 0.0,
                "selected_volume_sum": float(group["selected_volume"].sum()) if not group.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            BASE_VARIANT: "A Official hard 0.1",
            OFFICIAL_SOFT_VARIANT: "D Official soft 0.25",
            STAGE407_VARIANT: "B Stage407 hard 0.1",
            TARGET_VARIANT: "C Stage407 soft 0.25",
        }
    ).fillna(data["variant"])
    colors = {
        "A Official hard 0.1": "#ea580c",
        "D Official soft 0.25": "#a855f7",
        "B Stage407 hard 0.1": "#16a34a",
        "C Stage407 soft 0.25": "#2563eb",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label", sort=False):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
    axes[0].set_title("Stage409 / Script696: hard 0.1 loss-streak floor vs soft 0.25 staircase")
    axes[0].set_ylabel("Equity")
    axes[1].axhline(-30, color="#f59e0b", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("DD %")
    axes[2].axhline(90, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
    axes[2].set_title("Broker10 margin / equity")
    axes[2].set_ylabel("Margin %")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)

    fig2, ax = plt.subplots(figsize=(15, 7))
    for label, group in data.sort_values("date").groupby("label", sort=False):
        ax.plot(group["date"], group["account_equity"].astype(float), label=label, linewidth=1.8, color=colors.get(label))
    ax.axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.9, label="Initial capital")
    ax.axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
    ax.set_title("Stage409 Equity Curves: hard loss-streak floor vs soft staircase")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(loc="upper left")
    fig2.autofmt_xdate()
    fig2.tight_layout()
    fig2.savefig(EQUITY_CHART_PATH, dpi=170)
    plt.close(fig2)


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    window_growth: pd.DataFrame,
    entry_risk_summary: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def row(variant: str) -> dict[str, Any]:
        return summary[summary["variant"].eq(variant)].iloc[0].to_dict()

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    official = row(BASE_VARIANT)
    official_soft = row(OFFICIAL_SOFT_VARIANT)
    stage407 = row(STAGE407_VARIANT)
    target = row(TARGET_VARIANT)
    official_return = float(official["total_return_pct"])
    target_return = float(target["total_return_pct"])
    target_retention = target_return / official_return * 100.0 if official_return else 0.0
    stage407_return = float(stage407["total_return_pct"])

    cost2_target = cost[(cost["variant"].eq(TARGET_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].iloc[0]
    win = window_growth.set_index("variant") if not window_growth.empty else pd.DataFrame()
    stage407_window_growth = float(win.loc[STAGE407_VARIANT, "growth"]) if STAGE407_VARIANT in win.index else 0.0
    target_window_growth = float(win.loc[TARGET_VARIANT, "growth"]) if TARGET_VARIANT in win.index else 0.0
    official_window_growth = float(win.loc[BASE_VARIANT, "growth"]) if BASE_VARIANT in win.index else 0.0

    add(
        "stage407_soft_improves_stage407_full_return",
        "pass" if target_return > stage407_return else "fail",
        target_return - stage407_return,
        "> 0pp",
        "平滑连败风控应至少修复 Stage407 基线，而不是只增加风险。",
    )
    add(
        "stage407_soft_recovers_2025_window",
        "pass" if target_window_growth > stage407_window_growth + 1_000_000 else "watch",
        target_window_growth - stage407_window_growth,
        "> +1,000,000 CNY vs Stage407 in highlighted window",
        "重点验证 2025-04-16 至 2025-07-25 右尾参与权是否恢复。",
    )
    add(
        "stage407_soft_return_retention_vs_official",
        "pass" if target_retention >= 80.0 else "fail",
        target_retention,
        ">= 80%",
        "若仍远弱于正式版，只能说明机制有线索，不能晋级正式。",
    )
    add(
        "stage407_soft_dd_not_worse_than_stage407_by_3pp",
        "pass" if float(target["max_dd_pct"]) >= float(stage407["max_dd_pct"]) - 3.0 else "fail",
        float(target["max_dd_pct"]) - float(stage407["max_dd_pct"]),
        ">= -3pp",
        "不能用明显更大回撤换回收益。",
    )
    add(
        "stage407_soft_2x_cost_dd40",
        "pass" if float(cost2_target["max_dd_pct"]) >= -40.0 else "watch",
        float(cost2_target["max_dd_pct"]),
        ">= -40%",
        "成本压力不应明显失控。",
    )
    add(
        "official_soft_does_not_harm_official",
        "pass"
        if (
            float(official_soft["total_return_pct"]) >= float(official["total_return_pct"])
            and float(official_soft["max_dd_pct"]) >= float(official["max_dd_pct"]) - 3.0
        )
        else "watch",
        float(official_soft["total_return_pct"]) - float(official["total_return_pct"]),
        "return >= official and DD not worse by 3pp",
        "如果正式版套用平滑阶梯变差，不能把机制直接合入正式。",
    )
    add(
        "highlight_window_vs_official_gap",
        "pass" if target_window_growth >= official_window_growth * 0.6 else "watch",
        target_window_growth - official_window_growth,
        "target window growth >= 60% of official",
        "平滑后仍要接近正式版右尾，否则增长缺失没有真正修复。",
    )

    check_frame = pd.DataFrame(checks)
    hard_fail = check_frame[check_frame["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = check_frame[check_frame["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision = "stage407_soft_streak_not_promoted" if hard_fail else "stage407_soft_streak_watch_not_formal"
    return {
        "stage": "Stage409",
        "script_stage": "Stage696",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": BASE_VARIANT,
        "official_soft": OFFICIAL_SOFT_VARIANT,
        "stage407_baseline": STAGE407_VARIANT,
        "target": TARGET_VARIANT,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "candidate_hypothesis": (
                "Replace the discontinuous loss-streak risk cliff 1,1,1,0.1 with a simple staircase "
                "1,1,0.5,0.25, preserving loss protection while keeping trend right-tail participation."
            ),
            "streak_risk_multipliers_before": BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": SOFT_STREAK_MULTIPLIERS,
            "added_products": [JD_PRODUCT],
            "base_product_count": inputs["base_product_count"],
            "plus_product_count": inputs["plus_product_count"],
            "max_concurrent_positions_stage407": 5,
            "ai_top_n": AI_TOP_N,
            "ai_strategy": AI_STRATEGY,
            "highlight_window_start": WINDOW_START,
            "highlight_window_end": WINDOW_END,
        },
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "window_growth": window_growth.to_dict("records"),
        "entry_risk_summary": entry_risk_summary.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "daily": str(DAILY_PATH),
            "positions": str(POSITIONS_PATH),
            "product": str(PRODUCT_PATH),
            "product_delta": str(PRODUCT_DELTA_PATH),
            "product_margin": str(PRODUCT_MARGIN_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_risk_summary": str(ENTRY_RISK_SUMMARY_PATH),
            "window_growth": str(WINDOW_GROWTH_PATH),
            "window_product": str(WINDOW_PRODUCT_PATH),
            "forced_events": str(FORCED_EVENTS_PATH),
            "forced_summary": str(FORCED_SUMMARY_PATH),
            "ai_audit": str(AI_AUDIT_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
            "chart": str(CHART_PATH),
            "equity_chart": str(EQUITY_CHART_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    product_delta: pd.DataFrame,
    window_growth: pd.DataFrame,
    window_product: pd.DataFrame,
    entry_risk_summary: pd.DataFrame,
    forced_summary: pd.DataFrame,
    ai_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage409 / Script696 Stage407 Soft Loss-Streak Risk",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- A：当前正式版 Stage372/20w，正式 AI，`maxpos4`，原连败倍率 `1,1,1,0.1`。",
        "- D：当前正式版只把连败倍率改为 `1,1,0.5,0.25`。",
        "- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率 `1,1,1,0.1`。",
        "- C：B 只把连败倍率改为 `1,1,0.5,0.25`。",
        "- 2020-2021 因 full-market AI 预测未覆盖，沿用正式 AI 快照且不放行鸡蛋。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## Comparison",
        "",
        _md_table(comparison, max_rows=120),
        "",
        "## Highlight Window Growth",
        "",
        _md_table(window_growth, max_rows=40),
        "",
        "## Highlight Window Product Delta",
        "",
        _md_table(window_product, max_rows=80),
        "",
        "## Entry Risk Summary",
        "",
        _md_table(entry_risk_summary, max_rows=120),
        "",
        "## Annual",
        "",
        _md_table(annual, max_rows=120),
        "",
        "## Product Delta",
        "",
        _md_table(product_delta, max_rows=120),
        "",
        "## Forced Deleverage",
        "",
        _md_table(forced_summary),
        "",
        "## AI Audit",
        "",
        _md_table(ai_audit, max_rows=80),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- hard_fail_checks: `{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks: `{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inputs = _prepare_inputs()
    base_metadata = inputs["base_metadata"]
    plus_metadata = inputs["plus_metadata"]
    base_identity_map = s692.s653.s519._product_identity_cluster_map(base_metadata)
    plus_identity_map = s692.s653.s519._product_identity_cluster_map(plus_metadata)
    specs = [
        (_official_spec(base_identity_map), base_metadata),
        (_official_soft_spec(base_identity_map), base_metadata),
        (_stage407_spec(plus_identity_map, soft_streak=False), plus_metadata),
        (_stage407_spec(plus_identity_map, soft_streak=True), plus_metadata),
    ]

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    spec_objects = [item[0] for item in specs]
    for spec, metadata in specs:
        print(f"[stage696] running {spec.capital.variant}", flush=True)
        daily, positions, product_margin, usage, candidates, entry_risk, forced_events = _run_variant_with_diagnostics(
            spec,
            metadata,
        )
        daily_frames.append(daily)
        position_frames.append(positions)
        product_margin_frames.append(product_margin)
        if not usage.empty:
            usage_frames.append(usage)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_margin_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    entry_risk_all = pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = s692.s653._forced_summary(spec_objects, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = next(item[0] for item in specs if item[0].capital.variant == variant)
        for cost_multiplier in s692.s653.COST_MULTIPLIERS:
            metrics = s692.s653._metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(metrics)
            if cost_multiplier == 1.0:
                summary_rows.append(metrics)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    official_return = float(summary.loc[summary["variant"].eq(BASE_VARIANT), "total_return_pct"].iloc[0])
    for frame in (summary, cost):
        frame["return_retention_vs_official_pct"] = (
            pd.to_numeric(frame["total_return_pct"], errors="coerce").fillna(0.0) / official_return * 100.0
        ) if official_return else 0.0

    comparison = _comparison(summary, cost)
    annual, monthly = _annual_monthly(combo_daily)
    product = _product_summary(positions_all)
    product_delta = _product_delta(product)
    window_growth = _window_growth(combo_daily)
    window_product = _window_product(positions_all)
    entry_summary = _entry_risk_summary(candidates_all, entry_risk_all)
    _plot(combo_daily)
    decision = _decision(summary, cost, comparison, window_growth, entry_summary, inputs)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_RISK_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_DELTA_PATH, index=False, encoding="utf-8-sig")
    window_growth.to_csv(WINDOW_GROWTH_PATH, index=False, encoding="utf-8-sig")
    window_product.to_csv(WINDOW_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    _write_report(
        summary,
        cost,
        comparison,
        annual,
        product_delta,
        window_growth,
        window_product,
        entry_summary,
        forced_summary,
        inputs["ai_audit"],
        decision,
    )
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

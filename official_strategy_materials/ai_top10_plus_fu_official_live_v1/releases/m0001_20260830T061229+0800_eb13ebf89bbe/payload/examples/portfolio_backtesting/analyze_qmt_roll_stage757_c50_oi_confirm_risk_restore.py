from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import json

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage754_entry_oi_change_winner_loser as s754
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"
SOURCE_LINE_ID = "futures_trend_quarter_risk_no_streak"

OUTPUT_PREFIX = "qmt_roll_stage757_c50_oi_confirm_risk_restore"
MODEL_TAG = "stage757_c50_oi_confirm_risk_restore_v1"

BASE_VARIANT = s748.CANDIDATE_500K_VARIANT
CANDIDATE_VARIANT = "stage526_500k_force95_to80_r040_oi_confirm_r080_no_streak_no_recovery_stage757"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
RESTORE_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_group_stats_{MODEL_TAG}.csv"
RESTORE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_restore_lots_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _candidate_spec(metadata: dict[str, Any]) -> Any:
    base = s748._candidate_500k_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage757 C50 OI price confirm restores 0.80 risk",
        note=(
            "Stage748 C50 logic, but if the latest completed daily bar has OI up and price aligned "
            "with the trade direction, entry risk is doubled on top of the Stage748 0.40 risk ratio, "
            "which restores effective formal risk from 0.40 to 0.80."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_oi_price_confirm_risk_restore": True,
        "oi_price_confirm_risk_restore_multiplier": 2.00,
        "oi_price_confirm_risk_restore_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_r040_oi_r080_no_streak_stage757")


def _run_engine(spec: Any, metadata: dict[str, Any]) -> tuple[Any, dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    s719.s653.s517.assert_stage196_database_sentinels()
    s719.s653.s517.s506._patch_stage506_raw_roots()
    c3_overrides = s719.s513._c3_overrides(s719.s653.s517.START_DT)
    preload_start = max(s719.s653.s517.PRELOAD_START_DT, s719.s653.s517.START_DT - timedelta(days=365))
    _, open_map = s719.s653.s517.s506.s501._seed_proxy_maps()
    engine = s719.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s719.s653.s517.Interval.DAILY,
        start=preload_start,
        end=s719.s653.s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s719.s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s719.s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
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
        (daily.index >= s719.s653.s517.START_DT.date()) & (daily.index <= s719.s653.s517.END_DT.date())
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

    frames = s719._extract_raw_frames(engine, spec)
    positions = frames["positions"].copy()
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.capital.variant}")
    positions["combo_variant"] = spec.capital.variant
    positions["label"] = spec.capital.label
    positions["risk_multiplier"] = spec.capital.risk_multiplier
    c3_margin_daily, _product_margin = s719.s513._position_margin(positions, metadata)
    combined = s719.s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    strategy = getattr(engine, "strategy", None)
    for column, value in [
        ("forced_margin_deleverage_count", int(getattr(strategy, "forced_margin_deleverage_count", 0) or 0)),
        (
            "forced_margin_deleverage_closed_volume",
            int(getattr(strategy, "forced_margin_deleverage_closed_volume", 0) or 0),
        ),
        ("forced_margin_deleverage_ratio", float(getattr(strategy, "forced_margin_deleverage_ratio", 0.0) or 0.0)),
        (
            "forced_margin_deleverage_max_observed_ratio",
            float(getattr(strategy, "forced_margin_deleverage_max_observed_ratio", 0.0) or 0.0),
        ),
    ]:
        combined[column] = value
    forced_events = pd.DataFrame(getattr(strategy, "forced_margin_deleverage_events", []) if strategy else [])
    if not forced_events.empty:
        forced_events["variant"] = spec.capital.variant
        forced_events["label"] = spec.capital.label
        forced_events["profile"] = spec.profile
    return engine, frames, combined, forced_events


def _profit_label(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "unknown"
    if number > 0:
        return "profit"
    if number < 0:
        return "loss"
    return "flat"


def _risk_by_open_trade(trades: pd.DataFrame, entry_risk: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if trades.empty or entry_risk.empty:
        return {}
    trades_copy = trades.copy()
    trades_copy["datetime"] = pd.to_datetime(trades_copy["datetime"], errors="coerce")
    return s719._match_entry_risk_to_trades(trades_copy, entry_risk)


def _add_lot_features(
    closed: pd.DataFrame,
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
) -> pd.DataFrame:
    data = closed.copy()
    direction_sign = np.where(data["direction"].astype(str).eq("long"), 1.0, -1.0)
    data["theory_return_pct"] = (
        direction_sign
        * (pd.to_numeric(data["exit_price"], errors="coerce") - pd.to_numeric(data["entry_price"], errors="coerce"))
        / pd.to_numeric(data["entry_price"], errors="coerce")
        * 100.0
    )
    data["theory_outcome"] = data["theory_return_pct"].map(_profit_label)
    data["realized_outcome"] = data["realized_pnl"].map(_profit_label)

    risk_by_open = _risk_by_open_trade(trades, entry_risk)
    risk_fields = [
        "oi_price_confirm_risk_restore_enabled",
        "oi_price_confirm_risk_restore_applied",
        "oi_price_confirm_risk_restore_reason",
        "oi_price_confirm_risk_restore_base_multiplier",
        "oi_price_confirm_risk_restore_multiplier",
        "oi_price_confirm_risk_restore_effective_multiplier",
        "oi_price_confirm_entry_close",
        "oi_price_confirm_prev_close",
        "oi_price_confirm_entry_oi",
        "oi_price_confirm_prev_oi",
        "oi_price_confirm_oi_up",
        "oi_price_confirm_price_aligned",
        "oi_price_confirm_passed",
    ]
    for field in risk_fields:
        data[field] = [
            risk_by_open.get(str(open_trade_id), {}).get(field, np.nan)
            for open_trade_id in data["open_trade_id"].astype(str)
        ]

    feature_rows = [s754._entry_window_features(row) for _, row in data.iterrows()]
    return pd.concat([data.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)


def _stats_row(frame: pd.DataFrame, *, sample: str) -> dict[str, Any]:
    return {
        "sample": sample,
        "rows": int(len(frame)),
        "products": int(frame["product"].nunique()) if len(frame) and "product" in frame.columns else 0,
        "years": int(pd.to_datetime(frame["entry_date"]).dt.year.nunique()) if len(frame) else 0,
        "profit_count": int(frame["realized_outcome"].eq("profit").sum()) if len(frame) else 0,
        "loss_count": int(frame["realized_outcome"].eq("loss").sum()) if len(frame) else 0,
        "profit_rate_pct": float(frame["realized_outcome"].eq("profit").mean() * 100.0) if len(frame) else np.nan,
        "total_realized_pnl": float(pd.to_numeric(frame["realized_pnl"], errors="coerce").sum()) if len(frame) else 0.0,
        "avg_realized_pnl": float(pd.to_numeric(frame["realized_pnl"], errors="coerce").mean()) if len(frame) else np.nan,
        "median_realized_pnl": float(pd.to_numeric(frame["realized_pnl"], errors="coerce").median()) if len(frame) else np.nan,
        "avg_r_multiple": float(pd.to_numeric(frame["r_multiple"], errors="coerce").mean()) if len(frame) else np.nan,
        "median_r_multiple": float(pd.to_numeric(frame["r_multiple"], errors="coerce").median()) if len(frame) else np.nan,
        "avg_theory_return_pct": float(pd.to_numeric(frame["theory_return_pct"], errors="coerce").mean()) if len(frame) else np.nan,
        "median_theory_return_pct": (
            float(pd.to_numeric(frame["theory_return_pct"], errors="coerce").median()) if len(frame) else np.nan
        ),
    }


def _restore_group_stats(closed: pd.DataFrame) -> pd.DataFrame:
    applied = closed[pd.to_numeric(closed["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
    not_applied = closed[~pd.to_numeric(closed["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
    posthoc_hit = closed[pd.to_numeric(closed["entry_oi_price_confirm"], errors="coerce").eq(1)].copy()
    posthoc_miss = closed[
        closed["oi_available"].eq(1) & ~pd.to_numeric(closed["entry_oi_price_confirm"], errors="coerce").eq(1)
    ].copy()
    return pd.DataFrame(
        [
            _stats_row(closed, sample="all_closed_lots"),
            _stats_row(applied, sample="causal_oi_restore_applied"),
            _stats_row(not_applied, sample="causal_oi_restore_not_applied"),
            _stats_row(posthoc_hit, sample="posthoc_entry_day_oi_confirm_hit"),
            _stats_row(posthoc_miss, sample="posthoc_entry_day_oi_confirm_miss"),
        ]
    )


def _year_stats(closed: pd.DataFrame) -> pd.DataFrame:
    data = closed.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"]).dt.year
    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", sort=True):
        applied = group[pd.to_numeric(group["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
        not_applied = group[
            ~pd.to_numeric(group["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)
        ].copy()
        for label, subset in [("applied", applied), ("not_applied", not_applied)]:
            row = _stats_row(subset, sample=label)
            row["entry_year"] = int(year)
            rows.append(row)
    return pd.DataFrame(rows)


def _load_base_full_summary() -> pd.Series:
    frame = pd.read_csv(s748.SUMMARY_PATH, encoding="utf-8-sig")
    full = frame[
        frame["variant"].astype(str).eq(BASE_VARIANT)
        & frame["window_name"].astype(str).eq("full_2020_20260430")
    ].copy()
    if full.empty:
        raise FileNotFoundError(f"missing Stage748 full summary: {s748.SUMMARY_PATH}")
    return full.iloc[0]


def _comparison(base: pd.Series, candidate: pd.Series) -> pd.DataFrame:
    fields = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "forced_margin_deleverage_count",
    ]
    row: dict[str, Any] = {
        "base_variant": BASE_VARIANT,
        "candidate_variant": CANDIDATE_VARIANT,
    }
    for field in fields:
        row[f"base_{field}"] = base.get(field)
        row[f"candidate_{field}"] = candidate.get(field)
    row["delta_end_equity"] = float(candidate["end_equity"]) - float(base["end_equity"])
    row["delta_return_pct"] = float(candidate["total_return_pct"]) - float(base["total_return_pct"])
    row["delta_max_dd_pp"] = float(candidate["max_dd_pct"]) - float(base["max_dd_pct"])
    row["delta_sharpe"] = float(candidate["sharpe"]) - float(base["sharpe"])
    row["delta_slippage"] = float(candidate["total_slippage"]) - float(base["total_slippage"])
    row["delta_trade_count"] = float(candidate["total_trade_count"]) - float(base["total_trade_count"])
    return pd.DataFrame([row])


def _decision(comparison: pd.DataFrame, restore_group: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    cmp = comparison.iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if float(cmp["candidate_max_dd_pct"]) < -40.0:
        hard_fail.append("candidate_full_dd40_fail")
    if float(cmp["delta_max_dd_pp"]) < -3.0:
        hard_fail.append("candidate_dd_worse_more_than_3pp")
    if float(cmp["delta_sharpe"]) < -0.15:
        hard_fail.append("candidate_sharpe_worse_more_than_0_15")
    if float(cmp["delta_end_equity"]) <= 0.0:
        hard_fail.append("candidate_no_full_return_improvement")
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].iloc[0]
    if int(cost2["deployable_pass"]) != 1:
        hard_fail.append("candidate_cost2_deployable_fail")
    applied = restore_group[restore_group["sample"].eq("causal_oi_restore_applied")].iloc[0]
    if int(applied["rows"]) < 30:
        watch.append("restore_sample_lt30")
    if float(applied["profit_rate_pct"]) < 50.0:
        watch.append("restore_trade_winrate_lt50")
    return {
        "stage": "Stage757",
        "line_id": LINE_ID,
        "source_line_id": SOURCE_LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": "c50_oi_confirm_risk_restore_candidate_watch" if not hard_fail else "c50_oi_confirm_risk_restore_not_promoted",
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "base_risk_multiplier": 0.40,
            "restored_risk_multiplier": 0.80,
            "strategy_internal_restore_multiplier": 2.00,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_streak_entry_structure_risk_recovery": False,
            "enable_recovery_sleeve": False,
            "enable_oi_price_confirm_risk_restore": True,
            "causal_timing": "latest_completed_daily_bar",
        },
        "comparison": comparison.to_dict("records"),
        "restore_group": restore_group.to_dict("records"),
        "cost": cost.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "cost": str(COST_PATH),
            "curve": str(CURVE_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "restore_group": str(RESTORE_GROUP_PATH),
            "restore_lots": str(RESTORE_LOTS_PATH),
            "year": str(YEAR_PATH),
        },
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s719.s513._metadata()
    spec = _candidate_spec(metadata)
    engine, frames, combined, forced_events = _run_engine(spec, metadata)

    trades = frames["trades"]
    entry_risk = frames["entry_risk"]
    entry_candidates = frames["entry_candidates"]
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")

    row, curve, cost_rows = s748._metric_row(
        combined,
        spec=spec,
        window_name="full_2020_20260430",
        window_label="Full 2020-2026",
        window_group="full",
        forced_events=forced_events,
    )
    summary = pd.DataFrame([row])
    cost = pd.DataFrame(cost_rows)
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")

    closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    enriched = _add_lot_features(closed, trades, entry_risk)
    enriched.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")

    restore_group = _restore_group_stats(enriched)
    restore_group.to_csv(RESTORE_GROUP_PATH, index=False, encoding="utf-8-sig")
    restore_lots = enriched[pd.to_numeric(enriched["oi_price_confirm_risk_restore_applied"], errors="coerce").eq(1)].copy()
    restore_lots.to_csv(RESTORE_LOTS_PATH, index=False, encoding="utf-8-sig")
    year = _year_stats(enriched)
    year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")

    base = _load_base_full_summary()
    comparison = _comparison(base, summary.iloc[0])
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    decision = _decision(comparison, restore_group, cost)
    DECISION_PATH.write_text(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("SUMMARY")
    print(summary.to_string(index=False))
    print("\nCOMPARISON")
    print(comparison.to_string(index=False))
    print("\nRESTORE_GROUP")
    print(restore_group.to_string(index=False))
    print("\nYEAR")
    print(year.to_string(index=False))
    print("\nDECISION")
    print(json.dumps(s748._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

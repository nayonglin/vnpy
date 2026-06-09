from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_entry_risk_diagnostics_df, build_positions_df


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage705_stage407_jd_independent_sleeve_v1"
OUTPUT_PREFIX = "qmt_roll_stage705_stage407_jd_independent_sleeve"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 200_000.0
JD_PRODUCT = "jd.DCE"
WINDOW_START = s696.WINDOW_START
WINDOW_END = s696.WINDOW_END

BASE_VARIANT = s696.BASE_VARIANT
STAGE407_VARIANT = s696.STAGE407_VARIANT
SLEEVE20_VARIANT = "stage526_200k_core_unchanged_plus_jd_independent_sleeve20k"
SLEEVE50_VARIANT = "stage526_200k_core_unchanged_plus_jd_independent_sleeve50k"

AI_STRATEGY = "stage705_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage705_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage705_official_ai_pre_full_market_coverage"

GENERATED_DIR = OUTPUT_DIR / "stage705_generated_inputs"
JD_UNIVERSE_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_jd_only_universe_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SLEEVE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sleeve_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SLEEVE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sleeve_product_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
WINDOW_GROWTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_growth_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_only_{MODEL_TAG}.png"


@dataclass(frozen=True)
class SleeveSpec:
    variant: str
    label: str
    sleeve_capital: float
    note: str


SLEEVE_SPECS: tuple[SleeveSpec, ...] = (
    SleeveSpec(
        variant=SLEEVE20_VARIANT,
        label="C1 official core + jd independent sleeve20k",
        sleeve_capital=20_000.0,
        note="Official core path unchanged; jd.DCE trades in an independent 20k risk slot with its own risk state.",
    ),
    SleeveSpec(
        variant=SLEEVE50_VARIANT,
        label="C2 official core + jd independent sleeve50k",
        sleeve_capital=50_000.0,
        note="Same independent jd sleeve structure, enlarged to 50k as a fixed materiality stress test.",
    ),
)


def _json_safe(value: Any) -> Any:
    return s696._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s696._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _reconfigure_stage696_paths() -> None:
    s696.MODEL_TAG = MODEL_TAG
    s696.OUTPUT_PREFIX = OUTPUT_PREFIX
    s696.AI_STRATEGY = AI_STRATEGY
    s696.AI_SCORE_TYPE = AI_SCORE_TYPE
    s696.AI_PRE_COVERAGE_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s696.SOFT_STREAK_MULTIPLIERS = s696.BASE_STREAK_MULTIPLIERS
    s696.GENERATED_DIR = GENERATED_DIR
    s696.UNIVERSE_PLUS_JD_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
    s696.ELIGIBILITY_PATH = (
        GENERATED_DIR / f"{OUTPUT_PREFIX}_original_ai_plus_jd_rerank_top9_eligibility_{MODEL_TAG}.csv"
    )
    s696.MISSING_PREDICTION_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_missing_prediction_candidates_{MODEL_TAG}.csv"
    s696.AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_{MODEL_TAG}.csv"


def _write_jd_universe() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "product_vt_symbol": JD_PRODUCT,
                "product": "jd",
                "exchange": "DCE",
                "eligible": 1,
                "source": "stage705_jd_independent_sleeve",
            }
        ]
    ).to_csv(JD_UNIVERSE_PATH, index=False, encoding="utf-8-sig")


def _run_jd_sleeve(
    spec: SleeveSpec,
    metadata: dict[str, Any],
    identity_map: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s696.s692.s653.s517.assert_stage196_database_sentinels()
    s696.s692.s653.s517.s506._patch_stage506_raw_roots()
    base = s696._official_spec(identity_map)
    c3_overrides = s696.s692.s513._c3_overrides(s696.s692.s653.s517.START_DT)
    preload_start = max(
        s696.s692.s653.s517.PRELOAD_START_DT,
        s696.s692.s653.s517.START_DT - timedelta(days=365),
    )
    _, open_map = s696.s692.s653.s517.s506.s501._seed_proxy_maps()
    engine = s696.s692.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s696.s692.s653.s517.Interval.DAILY,
        start=preload_start,
        end=s696.s692.s653.s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.sleeve_capital,
    )
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(JD_UNIVERSE_PATH),
        "max_concurrent_positions": 1,
        "enable_ai_product_pool_filter": False,
        "ai_product_pool_eligibility_path": "",
        "ai_product_pool_strategy": "",
        "capital_base": spec.sleeve_capital,
    }
    setting = s696.s692.s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s696.s692.s653.s517.BASE_RISK_RATIO * float(base.capital.risk_multiplier),
        strategy_overrides={**c3_overrides, **overrides},
    )
    setting["capital_base"] = spec.sleeve_capital
    setting["sizing_equity_cap"] = spec.sleeve_capital
    setting.update(overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty jd sleeve daily: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= s696.s692.s653.s517.START_DT.date())
        & (daily.index <= s696.s692.s653.s517.END_DT.date())
    ].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["sleeve_equity"] = float(spec.sleeve_capital) + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["sleeve_capital"] = float(spec.sleeve_capital)
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if not positions.empty:
        positions["variant"] = spec.variant
        positions["combo_variant"] = spec.variant
        positions["label"] = spec.label
        positions["sleeve_capital"] = float(spec.sleeve_capital)

    candidates = build_entry_candidate_snapshots_df(engine)
    if not candidates.empty:
        candidates["variant"] = spec.variant
        candidates["label"] = spec.label
        candidates["sleeve_capital"] = float(spec.sleeve_capital)

    entry_risk = build_entry_risk_diagnostics_df(engine)
    if not entry_risk.empty:
        entry_risk["variant"] = spec.variant
        entry_risk["label"] = spec.label
        entry_risk["sleeve_capital"] = float(spec.sleeve_capital)

    forced_events = pd.DataFrame(getattr(engine.strategy, "forced_margin_deleverage_events", []))
    if not forced_events.empty:
        forced_events["variant"] = spec.variant
        forced_events["label"] = spec.label
    return daily, positions, candidates, entry_risk, forced_events


def _empty_margin_daily(variant: str, dates: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "variant": variant,
            "combo_variant": variant,
            "date": pd.to_datetime(dates, errors="coerce").dt.normalize(),
            "c3_margin_exact": 0.0,
            "c3_active_contracts": 0,
            "c3_active_products": 0,
        }
    )


def _combine_core_with_sleeves(
    core_daily: pd.DataFrame,
    sleeve_daily: pd.DataFrame,
    sleeve_margin_daily: pd.DataFrame,
) -> pd.DataFrame:
    rows = [core_daily.copy()]
    spec_map = {spec.variant: spec for spec in SLEEVE_SPECS}
    for variant, sleeve in sleeve_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        core = core_daily.copy().sort_values("date")
        sleeve_part = sleeve[["date", "net_pnl", "slippage", "trade_count", "sleeve_equity"]].rename(
            columns={
                "net_pnl": "sleeve_net_pnl",
                "slippage": "sleeve_slippage",
                "trade_count": "sleeve_trade_count",
            }
        )
        margin_part = sleeve_margin_daily[sleeve_margin_daily["variant"].eq(variant)][
            ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
        ].rename(
            columns={
                "c3_margin_exact": "sleeve_margin_exact",
                "c3_active_contracts": "sleeve_active_contracts",
                "c3_active_products": "sleeve_active_products",
            }
        )
        merged = core.merge(sleeve_part, on="date", how="left").merge(margin_part, on="date", how="left")
        for column in [
            "sleeve_net_pnl",
            "sleeve_slippage",
            "sleeve_trade_count",
            "sleeve_margin_exact",
            "sleeve_active_contracts",
            "sleeve_active_products",
        ]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["core_total_net_pnl"] = pd.to_numeric(merged["total_net_pnl"], errors="coerce").fillna(0.0)
        merged["core_total_slippage"] = pd.to_numeric(merged["total_slippage"], errors="coerce").fillna(0.0)
        merged["core_total_margin_exact"] = pd.to_numeric(merged["total_margin_exact"], errors="coerce").fillna(0.0)
        merged["total_net_pnl"] = merged["core_total_net_pnl"] + merged["sleeve_net_pnl"]
        merged["total_slippage"] = merged["core_total_slippage"] + merged["sleeve_slippage"]
        merged["trade_count"] = pd.to_numeric(merged["trade_count"], errors="coerce").fillna(0.0) + merged["sleeve_trade_count"]
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["core_total_margin_exact"] + merged["sleeve_margin_exact"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * float(
            s696.s692.s653.s517.BROKER_MARGIN_MULTIPLIER
        )
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        merged["variant"] = variant
        merged["combo_variant"] = variant
        merged["label"] = spec.label
        merged["sleeve_capital"] = float(spec.sleeve_capital)
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _metrics_spec(variant: str, label: str, note: str) -> s696.s692.s650.CapitalVariant:
    return s696.s692.s650.CapitalVariant(
        variant=variant,
        label=label,
        account_capital=ACCOUNT_CAPITAL,
        c3_capital=ACCOUNT_CAPITAL,
        risk_multiplier=0.80,
        product_cap_ratio=0.25,
        max_concurrent_positions=4,
        note=note,
    )


def _summary_and_cost(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in daily.groupby("variant", sort=False):
        label = str(frame["label"].dropna().iloc[0]) if "label" in frame and not frame["label"].dropna().empty else variant
        note = str(frame["note"].dropna().iloc[0]) if "note" in frame and not frame["note"].dropna().empty else ""
        spec = _metrics_spec(variant, label, note)
        for cost_multiplier in s696.s692.s653.COST_MULTIPLIERS:
            row = s696.s692.s650._metrics(frame, spec, cost_multiplier)
            row["profile"] = str(frame["profile"].dropna().iloc[0]) if "profile" in frame and not frame["profile"].dropna().empty else ""
            row["forced_margin_deleverage_count"] = int(
                pd.to_numeric(frame.get("forced_margin_deleverage_count", 0), errors="coerce").fillna(0).max()
            )
            row["forced_margin_deleverage_closed_volume"] = int(
                pd.to_numeric(frame.get("forced_margin_deleverage_closed_volume", 0), errors="coerce").fillna(0).max()
            )
            row["sleeve_capital"] = float(pd.to_numeric(frame.get("sleeve_capital", 0.0), errors="coerce").fillna(0.0).max())
            row["sleeve_total_pnl"] = float(pd.to_numeric(frame.get("sleeve_net_pnl", 0.0), errors="coerce").fillna(0.0).sum())
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    official_return = float(summary.loc[summary["variant"].eq(BASE_VARIANT), "total_return_pct"].iloc[0])
    for frame in (summary, cost):
        frame["return_retention_vs_official_pct"] = (
            pd.to_numeric(frame["total_return_pct"], errors="coerce").fillna(0.0) / official_return * 100.0
        ) if official_return else 0.0
    return summary, cost


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("stage407_shared_rerank_vs_official", BASE_VARIANT, STAGE407_VARIANT),
        ("jd_sleeve20_vs_official", BASE_VARIANT, SLEEVE20_VARIANT),
        ("jd_sleeve50_vs_official", BASE_VARIANT, SLEEVE50_VARIANT),
        ("jd_sleeve20_vs_stage407", STAGE407_VARIANT, SLEEVE20_VARIANT),
        ("jd_sleeve50_vs_stage407", STAGE407_VARIANT, SLEEVE50_VARIANT),
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
        ("days_over_100pct", "days_over_100pct"),
        ("sleeve_total_pnl", "sleeve_total_pnl"),
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
                rows.append(
                    {
                        "compare_name": compare_name,
                        "metric": f"{multiplier}x_cost_max_dd_pct",
                        "reference_variant": reference_variant,
                        "candidate_variant": candidate_variant,
                        "reference_value": float(ref_cost.loc[multiplier, "max_dd_pct"]),
                        "candidate_value": float(cand_cost.loc[multiplier, "max_dd_pct"]),
                        "delta": float(cand_cost.loc[multiplier, "max_dd_pct"] - ref_cost.loc[multiplier, "max_dd_pct"]),
                    }
                )
    return pd.DataFrame(rows)


def _window_growth(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for variant, group in data.groupby("variant", sort=False):
        window = group[
            (group["date"] >= pd.Timestamp(WINDOW_START)) & (group["date"] <= pd.Timestamp(WINDOW_END))
        ].sort_values("date")
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
                "slippage": float(pd.to_numeric(window.get("total_slippage", 0.0), errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _entry_summary(candidates: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not candidates.empty:
        cand = candidates.copy()
        cand["scope"] = "all_candidates"
        frames.append(cand)
    if not entry_risk.empty:
        risk = entry_risk.copy()
        risk["candidate_status"] = "opened"
        risk["is_opened"] = 1
        risk["scope"] = "opened_entries"
        frames.append(risk)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True, sort=False)
    for column in [
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "target_risk_amount",
        "estimated_equity",
        "loss_streak",
        "is_opened",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (variant, scope), group in data.groupby(["variant", "scope"], sort=True):
        zero = group[group["selected_volume"].le(0)]
        rows.append(
            {
                "variant": variant,
                "scope": scope,
                "rows": int(len(group)),
                "opened_rows": int(group["is_opened"].sum()),
                "zero_volume_rows": int(len(zero)),
                "risk_zero_margin_positive_rows": int(
                    len(zero[zero["contracts_by_risk"].le(0) & zero["contracts_by_margin"].gt(0)])
                ),
                "loss_streak_ge3_rows": int(len(group[group["loss_streak"].ge(3)])),
                "median_target_risk_amount": float(group["target_risk_amount"].median()) if not group.empty else 0.0,
                "median_selected_volume": float(group["selected_volume"].median()) if not group.empty else 0.0,
                "selected_volume_sum": float(group["selected_volume"].sum()) if not group.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _sleeve_product_summary(product_margin: pd.DataFrame) -> pd.DataFrame:
    if product_margin.empty:
        return pd.DataFrame()
    data = product_margin.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["year"] = data["date"].dt.year
    for column in ["net_pnl", "c3_margin_exact"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    return (
        data.groupby(["variant", "product_vt_symbol", "year"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            active_days=("active_product", "sum"),
            max_margin=("c3_margin_exact", "max"),
        )
        .sort_values(["variant", "year"])
    )


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, window_growth: pd.DataFrame) -> dict[str, Any]:
    by_variant = {variant: frame.iloc[0].to_dict() for variant, frame in summary.groupby("variant", sort=False)}
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    official = by_variant[BASE_VARIANT]
    rows: list[dict[str, Any]] = []
    for variant in [STAGE407_VARIANT, SLEEVE20_VARIANT, SLEEVE50_VARIANT]:
        if variant not in by_variant:
            continue
        item = dict(by_variant[variant])
        two_dd = float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0
        sleeve_pnl = float(item.get("sleeve_total_pnl", 0.0) or 0.0)
        no_degrade = int(
            variant != STAGE407_VARIANT
            and float(item["total_return_pct"]) >= float(official["total_return_pct"])
            and float(item["max_dd_pct"]) >= float(official["max_dd_pct"]) - 1.0
            and float(item["max_broker10_margin_to_equity_pct"]) <= 100.0
            and int(item["days_over_100pct"]) == 0
            and two_dd >= -40.0
            and sleeve_pnl > 0.0
        )
        rows.append(
            {
                "variant": variant,
                "end_equity": float(item["end_equity"]),
                "total_return_pct": float(item["total_return_pct"]),
                "max_dd_pct": float(item["max_dd_pct"]),
                "sharpe": float(item["sharpe"]),
                "max_broker10_margin_to_equity_pct": float(item["max_broker10_margin_to_equity_pct"]),
                "days_over_100pct": int(item["days_over_100pct"]),
                "two_x_max_dd_pct": two_dd,
                "sleeve_total_pnl": sleeve_pnl,
                "return_delta_vs_official_pp": float(item["total_return_pct"]) - float(official["total_return_pct"]),
                "end_equity_delta_vs_official": float(item["end_equity"]) - float(official["end_equity"]),
                "no_degrade_pass": no_degrade,
            }
        )
    window = window_growth.set_index("variant") if not window_growth.empty else pd.DataFrame()
    ranked = sorted(rows, key=lambda row: (row["no_degrade_pass"], row["end_equity_delta_vs_official"]), reverse=True)
    sleeve_pass = [row for row in ranked if row["variant"] in {SLEEVE20_VARIANT, SLEEVE50_VARIANT} and row["no_degrade_pass"]]
    decision = "jd_independent_sleeve_candidate_found" if sleeve_pass else "jd_independent_sleeve_watch_not_promoted"
    return {
        "stage": "Stage418",
        "script_stage": "Stage705",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "baseline": BASE_VARIANT,
        "shared_rerank_baseline": STAGE407_VARIANT,
        "candidate_variants": [SLEEVE20_VARIANT, SLEEVE50_VARIANT],
        "hypothesis": (
            "Keep the official core account and its global 0.1 loss-streak defense unchanged; "
            "let jd.DCE use a separate small risk slot so it cannot displace core AI products or pollute core loss streak."
        ),
        "pass_definition": (
            "Candidate must not reduce full-period return vs official, max drawdown must be no worse by more than 1pp, "
            "broker10 margin must stay <=100%, 2x cost DD must stay within -40%, and jd sleeve PnL must be positive."
        ),
        "ranked": ranked,
        "window_growth": window.reset_index().to_dict("records") if not window.empty else [],
        "redbox_growth": {
            variant: float(window.loc[variant, "growth"])
            for variant in window.index
            if variant in {BASE_VARIANT, STAGE407_VARIANT, SLEEVE20_VARIANT, SLEEVE50_VARIANT}
        }
        if not window.empty
        else {},
        "overfitting_reflection_before": (
            "No. The test is a predeclared capital isolation structure, not a product/month/rank patch."
        ),
        "overfitting_reflection_after_template": (
            "If the sleeve is only interpreted through one highlighted window or rescued by more sleeve sizes, it becomes overfit."
        ),
        "continued_value_template": (
            "Continue only if isolation improves the full path or clearly explains the failure. Do not tune sleeve capital after failure."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "daily": str(DAILY_PATH),
            "sleeve_daily": str(SLEEVE_DAILY_PATH),
            "positions": str(POSITIONS_PATH),
            "sleeve_product": str(SLEEVE_PRODUCT_PATH),
            "entry_summary": str(ENTRY_SUMMARY_PATH),
            "window_growth": str(WINDOW_GROWTH_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "equity_chart": str(EQUITY_CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(daily: pd.DataFrame) -> None:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    label_map = {
        BASE_VARIANT: "A Official core",
        STAGE407_VARIANT: "B Shared AI rerank top9",
        SLEEVE20_VARIANT: "C1 Core + JD sleeve20k",
        SLEEVE50_VARIANT: "C2 Core + JD sleeve50k",
    }
    colors = {
        "A Official core": "#ea580c",
        "B Shared AI rerank top9": "#16a34a",
        "C1 Core + JD sleeve20k": "#2563eb",
        "C2 Core + JD sleeve50k": "#a855f7",
    }
    data["plot_label"] = data["variant"].map(label_map).fillna(data["variant"])
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("plot_label", sort=False):
        equity = pd.to_numeric(group["account_equity"], errors="coerce").fillna(0.0)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    for ax in axes:
        ax.axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    axes[0].axhline(ACCOUNT_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage418/705: official core vs shared JD AI rerank vs independent JD sleeve")
    axes[0].set_ylabel("Equity")
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("DD %")
    axes[2].axhline(90, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].set_ylabel("Margin %")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)

    fig2, ax = plt.subplots(figsize=(15, 7))
    for label, group in data.sort_values("date").groupby("plot_label", sort=False):
        ax.plot(group["date"], group["account_equity"].astype(float), label=label, linewidth=1.8, color=colors.get(label))
    ax.axhline(ACCOUNT_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.9, label="Initial capital")
    ax.axvspan(pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END), color="#ef4444", alpha=0.10)
    ax.set_title("Stage418 Equity Curves: independent JD risk sleeve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(loc="upper left")
    fig2.autofmt_xdate()
    fig2.tight_layout()
    fig2.savefig(EQUITY_CHART_PATH, dpi=170)
    plt.close(fig2)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    window_growth: pd.DataFrame,
    sleeve_product: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct"]].rename(
        columns={"max_dd_pct": "cost2_max_dd_pct"}
    )
    view = summary.merge(cost2, on="variant", how="left")
    view = view[
        [
            "variant",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_official_pct",
            "max_dd_pct",
            "cost2_max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "sleeve_capital",
            "sleeve_total_pnl",
        ]
    ]
    lines = [
        "# Stage418 JD Independent Risk Sleeve",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- A：当前正式 Stage372/20w 原版，核心账户与全局连败 `0.1` 完全不动。",
        "- B：Stage407 共享主池，`jd.DCE` 参与原池 AI rerank top9 + maxpos5。",
        "- C1/C2：正式核心完全不动，`jd.DCE` 单独用 `20k/50k` 独立风险槽运行；账户资金仍按 20万合并评估。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        _md_table(view),
        "",
        "## Window Growth",
        "",
        _md_table(window_growth),
        "",
        "## Comparison",
        "",
        _md_table(comparison),
        "",
        "## JD Sleeve Product By Year",
        "",
        _md_table(sleeve_product),
        "",
        "## Entry Summary",
        "",
        _md_table(entry_summary),
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _reconfigure_stage696_paths()
    _write_jd_universe()
    inputs = s696._prepare_inputs()
    base_metadata = inputs["base_metadata"]
    plus_metadata = inputs["plus_metadata"]
    jd_metadata = s696.s692.s666.build_contract_metadata(supported_symbols=[JD_PRODUCT])
    base_identity_map = s696.s692.s653.s519._product_identity_cluster_map(base_metadata)
    plus_identity_map = s696.s692.s653.s519._product_identity_cluster_map(plus_metadata)
    jd_identity_map = s696.s692.s653.s519._product_identity_cluster_map(jd_metadata)

    specs = [
        (s696._official_spec(base_identity_map), base_metadata),
        (s696._stage407_spec(plus_identity_map, soft_streak=False), plus_metadata),
    ]

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    for spec, metadata in specs:
        print(f"[stage705] running {spec.capital.variant}", flush=True)
        daily, positions, product_margin, _usage, candidates, entry_risk, forced_events = s696._run_variant_with_diagnostics(
            spec,
            metadata,
        )
        daily_frames.append(daily)
        position_frames.append(positions)
        product_margin_frames.append(product_margin)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    sleeve_daily_frames: list[pd.DataFrame] = []
    sleeve_position_frames: list[pd.DataFrame] = []
    for sleeve_spec in SLEEVE_SPECS:
        print(f"[stage705] running {sleeve_spec.variant}", flush=True)
        daily, positions, candidates, entry_risk, forced_events = _run_jd_sleeve(sleeve_spec, jd_metadata, jd_identity_map)
        sleeve_daily_frames.append(daily)
        if not positions.empty:
            sleeve_position_frames.append(positions)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    base_daily_all = pd.concat(daily_frames, ignore_index=True, sort=False)
    official_daily = base_daily_all[base_daily_all["variant"].eq(BASE_VARIANT)].copy()
    sleeve_daily = pd.concat(sleeve_daily_frames, ignore_index=True, sort=False)
    sleeve_positions = pd.concat(sleeve_position_frames, ignore_index=True, sort=False) if sleeve_position_frames else pd.DataFrame()
    if sleeve_positions.empty:
        sleeve_margin_daily = pd.concat(
            [_empty_margin_daily(spec.variant, official_daily["date"]) for spec in SLEEVE_SPECS],
            ignore_index=True,
            sort=False,
        )
        sleeve_product = pd.DataFrame()
    else:
        sleeve_margin_daily, sleeve_product_margin = s696.s692.s513._position_margin(sleeve_positions, jd_metadata)
        sleeve_product = _sleeve_product_summary(sleeve_product_margin)

    combined_sleeve = _combine_core_with_sleeves(official_daily, sleeve_daily, sleeve_margin_daily)
    combo_daily = pd.concat(
        [
            base_daily_all[base_daily_all["variant"].isin([BASE_VARIANT, STAGE407_VARIANT])],
            combined_sleeve[combined_sleeve["variant"].isin([SLEEVE20_VARIANT, SLEEVE50_VARIANT])],
        ],
        ignore_index=True,
        sort=False,
    )
    positions_all = pd.concat(position_frames + sleeve_position_frames, ignore_index=True, sort=False)
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    entry_risk_all = pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()

    summary, cost = _summary_and_cost(combo_daily)
    comparison = _comparison(summary, cost)
    window_growth = _window_growth(combo_daily)
    entry_summary = _entry_summary(candidates_all, entry_risk_all)
    decision = _decision(summary, cost, window_growth)

    _plot(combo_daily)
    _write_report(summary, cost, comparison, window_growth, sleeve_product, entry_summary, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    sleeve_daily.to_csv(SLEEVE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    sleeve_product.to_csv(SLEEVE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    window_growth.to_csv(WINDOW_GROWTH_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

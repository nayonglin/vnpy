from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
import analyze_qmt_roll_stage705_stage407_jd_independent_sleeve as s705
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_entry_risk_diagnostics_df, build_positions_df


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage706_low_risk_scout_sleeve_v1"
OUTPUT_PREFIX = "qmt_roll_stage706_low_risk_scout_sleeve"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 200_000.0
WINDOW_START = s696.WINDOW_START
WINDOW_END = s696.WINDOW_END

BASE_VARIANT = s696.BASE_VARIANT
STAGE407_VARIANT = s696.STAGE407_VARIANT
OFFICIAL_SCOUT50_VARIANT = "stage526_200k_official_plus_low_risk_scout50k"
STAGE407_SCOUT50_VARIANT = "stage407_shared_ai_plus_low_risk_scout50k"

SOURCE_DAILY_PATH = s705.DAILY_PATH
SOURCE_CANDIDATES_PATH = s705.ENTRY_CANDIDATES_PATH

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SLEEVE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sleeve_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SLEEVE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sleeve_product_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
GATE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_events_{MODEL_TAG}.csv"
WINDOW_GROWTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_growth_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_only_{MODEL_TAG}.png"

SCOUT_CAPITAL = 50_000.0
SCOUT_MAXPOS = 2
SCOUT_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"
SCOUT_GATE_RISK_MULTIPLIER_MAX = 0.1000001


@dataclass(frozen=True)
class ScoutSpec:
    variant: str
    label: str
    source_variant: str
    output_variant: str
    source_label: str
    scout_label: str
    metadata_kind: str
    note: str


SCOUT_SPECS: tuple[ScoutSpec, ...] = (
    ScoutSpec(
        variant=OFFICIAL_SCOUT50_VARIANT,
        label="C1 official core + low-risk scout50k",
        source_variant=BASE_VARIANT,
        output_variant=OFFICIAL_SCOUT50_VARIANT,
        source_label="A Official core",
        scout_label="official risk-floor scout sleeve50k",
        metadata_kind="base",
        note=(
            "Official core is unchanged. A 50k independent scout sleeve may only trade official-core flat-entry "
            "candidates that the core saw at risk_multiplier<=0.1; the sleeve uses its own risk state."
        ),
    ),
    ScoutSpec(
        variant=STAGE407_SCOUT50_VARIANT,
        label="C2 Stage407 shared AI + low-risk scout50k",
        source_variant=STAGE407_VARIANT,
        output_variant=STAGE407_SCOUT50_VARIANT,
        source_label="B Stage407 shared AI rerank top9",
        scout_label="Stage407 risk-floor scout sleeve50k",
        metadata_kind="plus",
        note=(
            "Stage407 shared-AI core is unchanged. A 50k independent scout sleeve may only trade Stage407 "
            "risk-floor candidates, testing whether isolation can repair 0.1 underparticipation without "
            "changing the main path."
        ),
    ),
)


def _json_safe(value: Any) -> Any:
    return s705._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s705._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _candidate_key(row: pd.Series | dict[str, Any]) -> tuple[str, str, str, str]:
    date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    return (
        date,
        str(row["product_vt_symbol"]),
        str(row["direction"]),
        str(row["signal"]),
    )


def _context_key(context: Any, direction: str, signal: str) -> tuple[str, str, str, str]:
    return (
        pd.Timestamp(context.target_bar.datetime).normalize().strftime("%Y-%m-%d"),
        str(context.product_vt_symbol),
        str(direction),
        str(signal),
    )


def _load_source_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SOURCE_DAILY_PATH.exists() or not SOURCE_CANDIDATES_PATH.exists():
        raise FileNotFoundError(
            "Stage705 source outputs are required. Run analyze_qmt_roll_stage705_stage407_jd_independent_sleeve.py first."
        )
    daily = pd.read_csv(SOURCE_DAILY_PATH, encoding="utf-8-sig")
    candidates = pd.read_csv(SOURCE_CANDIDATES_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    return daily, candidates


def _low_risk_gate_events(candidates: pd.DataFrame, source_variant: str) -> pd.DataFrame:
    data = candidates[candidates["variant"].astype(str).eq(source_variant)].copy()
    for column in ["risk_multiplier", "selected_volume", "contracts_by_margin", "contracts_by_risk", "is_opened"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    data = data[
        data["entry_context"].astype(str).eq("flat_entry")
        & data["risk_multiplier"].le(SCOUT_GATE_RISK_MULTIPLIER_MAX)
        & data["passed_initial_filter"].fillna(0).astype(int).eq(1)
        & data["direction"].astype(str).isin(["long", "short"])
        & data["signal"].astype(str).ne("")
        & (
            data["is_opened"].eq(1)
            | data["selected_volume"].gt(0)
            | (data["contracts_by_risk"].le(0) & data["contracts_by_margin"].gt(0))
        )
    ].copy()
    if data.empty:
        return data
    data["gate_key"] = data.apply(lambda row: "|".join(_candidate_key(row)), axis=1)
    data["gate_source_variant"] = source_variant
    return data.sort_values(["date", "product_vt_symbol", "direction", "signal"]).reset_index(drop=True)


def _disable_plan(plan: dict[str, Any], reason: str) -> dict[str, Any]:
    sizing = dict(plan.get("sizing", {}))
    sizing["low_risk_scout_gate_enabled"] = 1
    sizing["low_risk_scout_gate_allowed"] = 0
    sizing["low_risk_scout_gate_reason"] = reason
    sizing["low_risk_scout_selected_volume_before_gate"] = int(sizing.get("selected_volume") or plan.get("volume") or 0)
    sizing["selected_volume"] = 0
    plan["sizing"] = sizing
    plan["volume"] = 0
    plan["native_openable"] = False
    plan["candidate_status"] = "skipped"
    plan["skip_reason"] = reason
    return plan


@contextmanager
def _patched_low_risk_scout_gate(allowed_keys: set[tuple[str, str, str, str]]) -> Iterable[None]:
    original = QmtRollPortfolioStrategy._build_flat_entry_candidate_plan

    def patched(self: QmtRollPortfolioStrategy, context: Any, base_active_positions: int) -> dict[str, Any] | None:
        plan = original(self, context, base_active_positions)
        if plan is None:
            return None
        key = _context_key(context, str(plan.get("direction", "")), str(plan.get("signal", "")))
        if key not in allowed_keys:
            return _disable_plan(plan, "low_risk_scout_gate_blocked")
        sizing = dict(plan.get("sizing", {}))
        sizing["low_risk_scout_gate_enabled"] = 1
        sizing["low_risk_scout_gate_allowed"] = 1
        sizing["low_risk_scout_gate_reason"] = "source_core_risk_floor_candidate"
        sizing["low_risk_scout_source_key"] = "|".join(key)
        plan["sizing"] = sizing
        return plan

    QmtRollPortfolioStrategy._build_flat_entry_candidate_plan = patched
    try:
        yield
    finally:
        QmtRollPortfolioStrategy._build_flat_entry_candidate_plan = original


def _run_scout_sleeve(
    spec: ScoutSpec,
    metadata: dict[str, Any],
    identity_map: str,
    allowed_keys: set[tuple[str, str, str, str]],
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
        capital=SCOUT_CAPITAL,
    )
    overrides = {
        **base.overrides,
        "max_concurrent_positions": SCOUT_MAXPOS,
        "enable_ai_product_pool_filter": False,
        "ai_product_pool_eligibility_path": "",
        "ai_product_pool_strategy": "",
        "capital_base": SCOUT_CAPITAL,
        "sizing_equity_cap": SCOUT_CAPITAL,
        "streak_risk_multipliers": SCOUT_STREAK_MULTIPLIERS,
    }
    if spec.metadata_kind == "plus":
        overrides["product_universe_csv_path"] = str(s696.UNIVERSE_PLUS_JD_PATH)
    setting = s696.s692.s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s696.s692.s653.s517.BASE_RISK_RATIO * 0.80,
        strategy_overrides={**c3_overrides, **overrides},
    )
    setting.update(overrides)
    with _patched_low_risk_scout_gate(allowed_keys):
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty scout sleeve daily: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= s696.s692.s653.s517.START_DT.date())
        & (daily.index <= s696.s692.s653.s517.END_DT.date())
    ].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["sleeve_equity"] = SCOUT_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.scout_label
    daily["sleeve_capital"] = SCOUT_CAPITAL
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if not positions.empty:
        positions["variant"] = spec.variant
        positions["combo_variant"] = spec.variant
        positions["label"] = spec.scout_label
        positions["sleeve_capital"] = SCOUT_CAPITAL
    candidates = build_entry_candidate_snapshots_df(engine)
    if not candidates.empty:
        candidates["variant"] = spec.variant
        candidates["label"] = spec.scout_label
        candidates["sleeve_capital"] = SCOUT_CAPITAL
    entry_risk = build_entry_risk_diagnostics_df(engine)
    if not entry_risk.empty:
        entry_risk["variant"] = spec.variant
        entry_risk["label"] = spec.scout_label
        entry_risk["sleeve_capital"] = SCOUT_CAPITAL
    forced_events = pd.DataFrame(getattr(engine.strategy, "forced_margin_deleverage_events", []))
    if not forced_events.empty:
        forced_events["variant"] = spec.variant
        forced_events["label"] = spec.scout_label
    return daily, positions, candidates, entry_risk, forced_events


def _combine_core_with_sleeve(
    source_daily: pd.DataFrame,
    sleeve_daily: pd.DataFrame,
    sleeve_margin_daily: pd.DataFrame,
    spec: ScoutSpec,
) -> pd.DataFrame:
    core = source_daily[source_daily["variant"].astype(str).eq(spec.source_variant)].copy().sort_values("date")
    stale_sleeve_columns = [
        "sleeve_net_pnl",
        "sleeve_slippage",
        "sleeve_trade_count",
        "sleeve_equity",
        "sleeve_margin_exact",
        "sleeve_active_contracts",
        "sleeve_active_products",
        "core_total_net_pnl",
        "core_total_slippage",
        "core_total_margin_exact",
        "sleeve_capital",
    ]
    core.drop(columns=[column for column in stale_sleeve_columns if column in core.columns], inplace=True)
    sleeve = sleeve_daily[sleeve_daily["variant"].astype(str).eq(spec.variant)][
        ["date", "net_pnl", "slippage", "trade_count", "sleeve_equity"]
    ].rename(
        columns={
            "net_pnl": "sleeve_net_pnl",
            "slippage": "sleeve_slippage",
            "trade_count": "sleeve_trade_count",
        }
    )
    margin = sleeve_margin_daily[sleeve_margin_daily["variant"].astype(str).eq(spec.variant)][
        ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
    ].rename(
        columns={
            "c3_margin_exact": "sleeve_margin_exact",
            "c3_active_contracts": "sleeve_active_contracts",
            "c3_active_products": "sleeve_active_products",
        }
    )
    merged = core.merge(sleeve, on="date", how="left").merge(margin, on="date", how="left")
    for column in [
        "sleeve_net_pnl",
        "sleeve_slippage",
        "sleeve_trade_count",
        "sleeve_margin_exact",
        "sleeve_active_contracts",
        "sleeve_active_products",
    ]:
        if column not in merged.columns:
            merged[column] = 0.0
        else:
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["core_total_net_pnl"] = pd.to_numeric(merged["total_net_pnl"], errors="coerce").fillna(0.0)
    merged["core_total_slippage"] = pd.to_numeric(merged["total_slippage"], errors="coerce").fillna(0.0)
    merged["core_total_margin_exact"] = pd.to_numeric(merged["total_margin_exact"], errors="coerce").fillna(0.0)
    merged["total_net_pnl"] = merged["core_total_net_pnl"] + merged["sleeve_net_pnl"]
    merged["total_slippage"] = merged["core_total_slippage"] + merged["sleeve_slippage"]
    merged["trade_count"] = pd.to_numeric(merged["trade_count"], errors="coerce").fillna(0.0) + merged["sleeve_trade_count"]
    merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
    merged["total_margin_exact"] = merged["core_total_margin_exact"] + merged["sleeve_margin_exact"]
    merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * float(s696.s692.s653.s517.BROKER_MARGIN_MULTIPLIER)
    merged["broker10_margin_to_equity_pct"] = (
        merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    merged["variant"] = spec.output_variant
    merged["combo_variant"] = spec.output_variant
    merged["label"] = spec.label
    merged["sleeve_capital"] = SCOUT_CAPITAL
    merged["note"] = spec.note
    return merged


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
        ("official_scout_vs_official", BASE_VARIANT, OFFICIAL_SCOUT50_VARIANT),
        ("stage407_vs_official", BASE_VARIANT, STAGE407_VARIANT),
        ("stage407_scout_vs_stage407", STAGE407_VARIANT, STAGE407_SCOUT50_VARIANT),
        ("stage407_scout_vs_official", BASE_VARIANT, STAGE407_SCOUT50_VARIANT),
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
        .sort_values(["variant", "year", "net_pnl"], ascending=[True, True, False])
    )


def _gate_summary(gate_events: pd.DataFrame) -> pd.DataFrame:
    if gate_events.empty:
        return pd.DataFrame()
    data = gate_events.copy()
    data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    return (
        data.groupby(["gate_source_variant", "year"], as_index=False)
        .agg(
            rows=("gate_key", "count"),
            products=("product_vt_symbol", "nunique"),
            opened_rows=("is_opened", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            median_selected_volume=("selected_volume", "median"),
        )
        .sort_values(["gate_source_variant", "year"])
    )


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, window_growth: pd.DataFrame, gate_events: pd.DataFrame) -> dict[str, Any]:
    by_variant = {variant: frame.iloc[0].to_dict() for variant, frame in summary.groupby("variant", sort=False)}
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    official = by_variant[BASE_VARIANT]
    rows: list[dict[str, Any]] = []
    for variant in [OFFICIAL_SCOUT50_VARIANT, STAGE407_SCOUT50_VARIANT]:
        item = by_variant.get(variant)
        if not item:
            continue
        two_dd = float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0
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
                "sleeve_total_pnl": float(item.get("sleeve_total_pnl", 0.0) or 0.0),
                "return_delta_vs_official_pp": float(item["total_return_pct"]) - float(official["total_return_pct"]),
                "end_equity_delta_vs_official": float(item["end_equity"]) - float(official["end_equity"]),
            }
        )
    official_candidate = next((row for row in rows if row["variant"] == OFFICIAL_SCOUT50_VARIANT), None)
    promoted = bool(
        official_candidate
        and official_candidate["end_equity_delta_vs_official"] > 0.0
        and official_candidate["max_dd_pct"] >= float(official["max_dd_pct"]) - 1.0
        and official_candidate["max_broker10_margin_to_equity_pct"] <= 100.0
        and official_candidate["two_x_max_dd_pct"] >= -40.0
        and official_candidate["sleeve_total_pnl"] >= 2_000.0
    )
    return {
        "stage": "Stage420",
        "script_stage": "Stage706",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "low_risk_scout_sleeve_candidate_found" if promoted else "low_risk_scout_sleeve_not_promoted",
        "baseline": BASE_VARIANT,
        "diagnostic_baseline": STAGE407_VARIANT,
        "candidate_variants": [OFFICIAL_SCOUT50_VARIANT, STAGE407_SCOUT50_VARIANT],
        "hypothesis": (
            "Keep the main account 0.1 loss-streak defense unchanged, but reserve one independent 50k scout sleeve "
            "for flat-entry candidates that the source core itself saw under risk_multiplier<=0.1. This tests whether "
            "right-tail participation can be restored without weakening the main account defense."
        ),
        "pass_definition": (
            "The official+scout candidate must beat official end equity, avoid worsening max DD by more than 1pp, "
            "keep broker10 margin <=100%, keep 2x-cost DD within -40%, and produce at least 2,000 sleeve PnL."
        ),
        "ranked": rows,
        "gate_summary": _gate_summary(gate_events).to_dict("records"),
        "window_growth": window_growth.to_dict("records") if not window_growth.empty else [],
        "overfitting_reflection_before": (
            "No. The gate is defined by the source core's own risk-floor state and not by product, year, or the redbox window."
        ),
        "overfitting_reflection_after_template": (
            "If this fails, tuning sleeve capital, maxpos, products, or dates would be overfit; the structure itself must carry."
        ),
        "continued_value_template": (
            "Continue only if the official+scout arm materially improves full-cycle path. A redbox-only repair is diagnostic, not promotable."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "daily": str(DAILY_PATH),
            "sleeve_daily": str(SLEEVE_DAILY_PATH),
            "positions": str(POSITIONS_PATH),
            "sleeve_product": str(SLEEVE_PRODUCT_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "gate_events": str(GATE_EVENTS_PATH),
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
        BASE_VARIANT: "A Official",
        OFFICIAL_SCOUT50_VARIANT: "C1 Official + scout50k",
        STAGE407_VARIANT: "B Stage407",
        STAGE407_SCOUT50_VARIANT: "C2 Stage407 + scout50k",
    }
    colors = {
        "A Official": "#ea580c",
        "C1 Official + scout50k": "#2563eb",
        "B Stage407": "#16a34a",
        "C2 Stage407 + scout50k": "#a855f7",
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
    axes[0].set_title("Stage420/706: low-risk scout sleeve")
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
    ax.set_title("Stage420 Equity Curves: low-risk scout sleeve")
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
    gate_events: pd.DataFrame,
    sleeve_product: pd.DataFrame,
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
    gate_view = _gate_summary(gate_events)
    lines = [
        "# Stage420 Low-Risk Scout Sleeve",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- A：当前正式 Stage372/20w 原版。",
        "- B：Stage407 共享主池诊断基准。",
        "- C1：正式核心不动 + 50k 独立低风险候选补偿槽。",
        "- C2：Stage407 主路径不动 + 50k 独立低风险候选补偿槽。",
        "- 补偿槽只允许交易源核心已出现 `risk_multiplier<=0.1` 的 flat-entry 候选；槽内关闭自身连败降风险，只靠固定 50k、maxpos2 和原始入场/止损约束限制风险。",
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
        "## Gate Summary",
        "",
        _md_table(gate_view),
        "",
        "## Sleeve Product By Year",
        "",
        _md_table(sleeve_product, max_rows=80),
        "",
        "## Decision",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    s705._reconfigure_stage696_paths()
    source_daily, source_candidates = _load_source_data()
    inputs = s696._prepare_inputs()
    base_metadata = inputs["base_metadata"]
    plus_metadata = inputs["plus_metadata"]
    base_identity_map = s696.s692.s653.s519._product_identity_cluster_map(base_metadata)
    plus_identity_map = s696.s692.s653.s519._product_identity_cluster_map(plus_metadata)

    gate_frames: list[pd.DataFrame] = []
    sleeve_daily_frames: list[pd.DataFrame] = []
    sleeve_position_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []

    for spec in SCOUT_SPECS:
        gate = _low_risk_gate_events(source_candidates, spec.source_variant)
        gate_frames.append(gate)
        allowed_keys = {_candidate_key(row) for _, row in gate.iterrows()}
        metadata = plus_metadata if spec.metadata_kind == "plus" else base_metadata
        identity_map = plus_identity_map if spec.metadata_kind == "plus" else base_identity_map
        print(f"[stage706] running {spec.variant} allowed_keys={len(allowed_keys)}", flush=True)
        daily, positions, candidates, entry_risk, _forced = _run_scout_sleeve(spec, metadata, identity_map, allowed_keys)
        sleeve_daily_frames.append(daily)
        if not positions.empty:
            sleeve_position_frames.append(positions)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)

    gate_events = pd.concat(gate_frames, ignore_index=True, sort=False) if gate_frames else pd.DataFrame()
    sleeve_daily = pd.concat(sleeve_daily_frames, ignore_index=True, sort=False) if sleeve_daily_frames else pd.DataFrame()
    sleeve_positions = pd.concat(sleeve_position_frames, ignore_index=True, sort=False) if sleeve_position_frames else pd.DataFrame()
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    entry_risk_all = pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()

    if sleeve_positions.empty:
        official_dates = source_daily[source_daily["variant"].eq(BASE_VARIANT)]["date"]
        sleeve_margin_daily = pd.concat(
            [_empty_margin_daily(spec.variant, official_dates) for spec in SCOUT_SPECS],
            ignore_index=True,
            sort=False,
        )
        sleeve_product = pd.DataFrame()
    else:
        metadata_for_margin = {
            "sizes": {**base_metadata["sizes"], **plus_metadata["sizes"]},
            "margin_ratios": {**base_metadata["margin_ratios"], **plus_metadata["margin_ratios"]},
        }
        sleeve_margin_daily, sleeve_product_margin = s696.s692.s513._position_margin(sleeve_positions, metadata_for_margin)
        sleeve_product = _sleeve_product_summary(sleeve_product_margin)

    base_rows = source_daily[source_daily["variant"].isin([BASE_VARIANT, STAGE407_VARIANT])].copy()
    combo_rows = [base_rows]
    for spec in SCOUT_SPECS:
        combo_rows.append(_combine_core_with_sleeve(source_daily, sleeve_daily, sleeve_margin_daily, spec))
    combo_daily = pd.concat(combo_rows, ignore_index=True, sort=False)

    summary, cost = _summary_and_cost(combo_daily)
    comparison = _comparison(summary, cost)
    window_growth = _window_growth(combo_daily)
    decision = _decision(summary, cost, window_growth, gate_events)

    _plot(combo_daily)
    _write_report(summary, cost, comparison, window_growth, gate_events, sleeve_product, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    sleeve_daily.to_csv(SLEEVE_DAILY_PATH, index=False, encoding="utf-8-sig")
    sleeve_positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    sleeve_product.to_csv(SLEEVE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    gate_events.to_csv(GATE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    window_growth.to_csv(WINDOW_GROWTH_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

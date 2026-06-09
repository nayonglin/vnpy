from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage666_stage372_500k_risk005_ag_ab as s666
from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import (
    PREDICTIONS_OUTPUT_PATH as FULL_MARKET_AI_PREDICTIONS_PATH,
)
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, OFFICIAL_LIVE_PROFILE_NAME


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage692_official_stage372_jd_top9_maxpos5_v1"
OUTPUT_PREFIX = "qmt_roll_stage692_official_stage372_jd_top9_maxpos5"

LINE_ID = "futures_trend_drawdown30_preserve_return"
BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
MAXPOS5_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos5"
TARGET_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_plus_jd_ai_top9_maxpos5"
JD_PRODUCT = "jd.DCE"
AI_TOP_N = 9
AI_TOP9_STRATEGY = "stage692_official_stage372_plus_jd_full_market_ai_top9_entry_filter"
AI_TOP9_SCORE_TYPE = "stage692_full_market_ai_probability_top9"
AI_TOP9_OFFICIAL_PRE2022_SCORE_TYPE = "stage692_official_ai_pre_full_market_coverage"

GENERATED_DIR = OUTPUT_DIR / "stage692_generated_inputs"
UNIVERSE_PLUS_JD_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
ELIGIBILITY_TOP9_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_ai_top9_eligibility_{MODEL_TAG}.csv"

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
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_top9_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _official_spec(identity_map: str) -> s653.ForcedVariant:
    spec = s659._official_live_spec(identity_map)
    overrides = {
        **spec.overrides,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
    }
    return replace(spec, overrides=overrides)


def _maxpos5_spec(identity_map: str) -> s653.ForcedVariant:
    base = _official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=MAXPOS5_VARIANT,
        label="Stage405 official Stage372 20w recovery sleeve maxpos5",
        max_concurrent_positions=5,
        note="Stage692 B: keep official Stage372 logic and AI pool; only relax max_concurrent_positions from 4 to 5.",
    )
    overrides = {**base.overrides, "max_concurrent_positions": 5}
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_recovery_sleeve_maxpos5")


def _target_spec(identity_map: str) -> s653.ForcedVariant:
    base = _official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=TARGET_VARIANT,
        label="Stage405 official Stage372 plus jd AI top9 maxpos5",
        max_concurrent_positions=5,
        note=(
            "Stage692 C: add jd.DCE to the product universe, use full-market AI top9 monthly eligibility "
            "where available, and relax max_concurrent_positions from 4 to 5."
        ),
    )
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(UNIVERSE_PLUS_JD_PATH),
        "max_concurrent_positions": 5,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_TOP9_PATH),
        "ai_product_pool_strategy": AI_TOP9_STRATEGY,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_plus_jd_ai_top9_maxpos5")


def _write_plus_jd_universe(base_symbols: list[str]) -> dict[str, Any]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    base_set = set(base_symbols)
    plus_symbols = sorted(base_set | {JD_PRODUCT})
    rows: list[dict[str, Any]] = []
    for symbol in plus_symbols:
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage692_official_stage372_plus_jd_ai_top9",
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PLUS_JD_PATH, index=False, encoding="utf-8-sig")
    return {
        "base_symbols": sorted(base_set),
        "plus_symbols": plus_symbols,
        "effective_new_products": sorted({JD_PRODUCT} - base_set),
        "already_in_base": sorted(base_set & {JD_PRODUCT}),
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
    official["strategy"] = AI_TOP9_STRATEGY
    official["score_type"] = AI_TOP9_OFFICIAL_PRE2022_SCORE_TYPE
    for column in ["score", "score_rank", "top_n"]:
        official[column] = pd.to_numeric(official[column], errors="coerce").fillna(0.0)
    official["top_n"] = official.groupby("eval_date")["product_vt_symbol"].transform("count")
    return official[list(required)].copy()


def _write_ai_top9_eligibility(symbols: list[str]) -> pd.DataFrame:
    predictions = pd.read_csv(
        FULL_MARKET_AI_PREDICTIONS_PATH,
        usecols=["eval_date", "product_vt_symbol", PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN],
    )
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    predictions = predictions[predictions["product_vt_symbol"].astype(str).isin(set(symbols))].copy()
    if predictions.empty:
        raise RuntimeError("no full-market AI prediction rows for Stage692 plus-jd universe")

    rows: list[dict[str, Any]] = []
    for eval_date, group in predictions.groupby("eval_date", sort=True):
        ranked = group.sort_values(
            [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        ranked["score_rank"] = range(1, len(ranked) + 1)
        selected = ranked.head(AI_TOP_N).copy()
        for row in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": AI_TOP9_STRATEGY,
                    "score_type": AI_TOP9_SCORE_TYPE,
                    "eval_date": str(eval_date),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, PROBABILITY_COLUMN)),
                    "score_rank": int(getattr(row, "score_rank")),
                    "top_n": AI_TOP_N,
                }
            )

    full_market_rows = pd.DataFrame(rows)
    first_full_market_eval = str(full_market_rows["eval_date"].min())
    pre_rows = _official_pre_full_market_rows(first_full_market_eval)
    eligibility = pd.concat([pre_rows, full_market_rows], ignore_index=True, sort=False)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    eligibility.reset_index(drop=True, inplace=True)
    ELIGIBILITY_TOP9_PATH.parent.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(ELIGIBILITY_TOP9_PATH, index=False, encoding="utf-8-sig")
    return eligibility


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = s666._official_symbols()
    universe = _write_plus_jd_universe(base_symbols)
    eligibility = _write_ai_top9_eligibility(universe["plus_symbols"])
    base_metadata = s666.build_contract_metadata(supported_symbols=universe["base_symbols"])
    plus_metadata = s666.build_contract_metadata(supported_symbols=universe["plus_symbols"])
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
        "eligibility_path": str(ELIGIBILITY_TOP9_PATH),
        "full_market_predictions_path": str(FULL_MARKET_AI_PREDICTIONS_PATH),
    }


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


def _run_spec(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily, positions, usage, forced_events = s653._run_variant(spec, metadata)
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, positions, product_margin, usage, forced_events


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    by_variant = {variant: frame.iloc[0].to_dict() for variant, frame in summary.groupby("variant", sort=False)}
    cost_by_variant = {
        variant: frame.set_index("cost_multiplier") for variant, frame in cost.groupby("variant", sort=False)
    }
    pairs = [
        ("official_vs_maxpos5", BASE_VARIANT, MAXPOS5_VARIANT),
        ("maxpos5_vs_plus_jd_ai_top9", MAXPOS5_VARIANT, TARGET_VARIANT),
        ("official_vs_plus_jd_ai_top9", BASE_VARIANT, TARGET_VARIANT),
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


def _annual_monthly(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce").fillna(0.0)
    data["trade_count"] = pd.to_numeric(data.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    data["slippage"] = pd.to_numeric(data.get("slippage", 0.0), errors="coerce").fillna(0.0)

    def summarize(frame: pd.DataFrame, key: str, label: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for (variant, period), group in frame.groupby(["variant", key], sort=True):
            group = group.sort_values("date")
            equity = group["account_equity"].astype(float)
            peak = equity.cummax()
            dd = ((equity - peak) / peak.replace(0.0, pd.NA) * 100.0).min()
            start_equity = float(equity.iloc[0])
            end_equity = float(equity.iloc[-1])
            rows.append(
                {
                    "variant": variant,
                    label: period,
                    "period_start_equity": start_equity,
                    "period_end_equity": end_equity,
                    "period_pnl": float(end_equity - start_equity),
                    "period_return_pct": float((end_equity / start_equity - 1.0) * 100.0) if start_equity else 0.0,
                    "period_max_dd_pct": float(dd or 0.0),
                    "total_trade_count": float(group["trade_count"].sum()),
                    "total_slippage": float(group["slippage"].sum()),
                }
            )
        return pd.DataFrame(rows)

    data["year"] = data["date"].dt.year
    data["month"] = data["date"].dt.strftime("%Y-%m")
    return summarize(data, "year", "year"), summarize(data, "month", "month")


def _product_summary(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    data = positions.copy()
    data["product"] = data["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False).str.lower()
    for column in ["net_pnl", "slippage", "trade_count", "end_pos"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    active = data[data["end_pos"].abs().gt(0)].copy()
    rows: list[dict[str, Any]] = []
    for (variant, product), group in data.groupby(["variant", "product"], sort=True):
        active_group = active[(active["variant"].eq(variant)) & (active["product"].eq(product))]
        rows.append(
            {
                "variant": variant,
                "product": product,
                "net_pnl": float(group["net_pnl"].sum()),
                "slippage": float(group["slippage"].sum()),
                "trade_count": float(group["trade_count"].sum()),
                "active_days": int(pd.to_datetime(active_group.get("date"), errors="coerce").dt.normalize().nunique())
                if not active_group.empty
                else 0,
            }
        )
    return pd.DataFrame(rows)


def _product_delta(product: pd.DataFrame) -> pd.DataFrame:
    if product.empty:
        return pd.DataFrame()
    key = ["product"]
    base = product[product["variant"].eq(BASE_VARIANT)].set_index(key)
    maxpos = product[product["variant"].eq(MAXPOS5_VARIANT)].set_index(key)
    target = product[product["variant"].eq(TARGET_VARIANT)].set_index(key)
    products = sorted(set(base.index) | set(maxpos.index) | set(target.index))
    rows: list[dict[str, Any]] = []
    for product_key in products:
        product_name = product_key[0] if isinstance(product_key, tuple) else str(product_key)
        base_pnl = float(base.loc[product_key, "net_pnl"]) if product_key in base.index else 0.0
        maxpos_pnl = float(maxpos.loc[product_key, "net_pnl"]) if product_key in maxpos.index else 0.0
        target_pnl = float(target.loc[product_key, "net_pnl"]) if product_key in target.index else 0.0
        rows.append(
            {
                "product": product_name,
                "official_net_pnl": base_pnl,
                "maxpos5_net_pnl": maxpos_pnl,
                "target_net_pnl": target_pnl,
                "delta_target_vs_official": target_pnl - base_pnl,
                "delta_target_vs_maxpos5": target_pnl - maxpos_pnl,
            }
        )
    return pd.DataFrame(rows).sort_values("delta_target_vs_official")


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            BASE_VARIANT: "Official maxpos4",
            MAXPOS5_VARIANT: "Official maxpos5",
            TARGET_VARIANT: "Plus jd AI top9 maxpos5",
        }
    ).fillna(data["variant"])
    colors = {
        "Official maxpos4": "#f97316",
        "Official maxpos5": "#2563eb",
        "Plus jd AI top9 maxpos5": "#16a34a",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label"):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage405 official Stage372 plus jd AI top9 maxpos5")
    axes[0].set_ylabel("Equity")
    axes[1].axhline(-30, color="#f59e0b", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("DD %")
    axes[2].axhline(90, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].set_title("Broker10 margin / equity")
    axes[2].set_ylabel("Margin %")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    product_delta: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    target = summary[summary["variant"].eq(TARGET_VARIANT)].iloc[0]
    official = summary[summary["variant"].eq(BASE_VARIANT)].iloc[0]
    target_cost2 = cost[(cost["variant"].eq(TARGET_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].iloc[0]
    official_return = float(official["total_return_pct"])
    target_return = float(target["total_return_pct"])
    return_retention = target_return / official_return * 100.0 if official_return else 0.0
    official_cmp = comparison[
        comparison["compare_name"].eq("official_vs_plus_jd_ai_top9") & comparison["metric"].eq("return_pct")
    ]
    maxpos_cmp = comparison[
        comparison["compare_name"].eq("maxpos5_vs_plus_jd_ai_top9") & comparison["metric"].eq("return_pct")
    ]
    jd_selected_rate = (
        float(inputs["ai_audit"]["jd_selected"].mean() * 100.0) if not inputs["ai_audit"].empty else 0.0
    )
    jd_pnl = 0.0
    if not product_delta.empty and "jd" in set(product_delta["product"].astype(str)):
        jd_pnl = float(product_delta[product_delta["product"].eq("jd")]["target_net_pnl"].iloc[0])

    add(
        "target_return_retention_vs_official",
        "pass" if return_retention >= 80.0 else "fail",
        return_retention,
        ">= 80%",
        "候选不能只靠牺牲主要右尾换来更多机会。",
    )
    add(
        "target_return_improves_vs_official",
        "pass" if not official_cmp.empty and float(official_cmp["delta"].iloc[0]) > 0.0 else "fail",
        float(official_cmp["delta"].iloc[0]) if not official_cmp.empty else 0.0,
        "> 0pp",
        "新增鸡蛋+top9+maxpos5 至少应优于当前正式版。",
    )
    add(
        "target_return_improves_vs_maxpos5_only",
        "pass" if not maxpos_cmp.empty and float(maxpos_cmp["delta"].iloc[0]) > 0.0 else "fail",
        float(maxpos_cmp["delta"].iloc[0]) if not maxpos_cmp.empty else 0.0,
        "> 0pp",
        "鸡蛋+AI top9 的边际贡献应优于只放宽 maxpos。",
    )
    add(
        "target_dd_not_materially_worse",
        "pass" if float(target["max_dd_pct"]) >= float(official["max_dd_pct"]) - 3.0 else "fail",
        float(target["max_dd_pct"] - official["max_dd_pct"]),
        ">= -3pp vs official",
        "最大回撤不能明显劣化。",
    )
    add(
        "target_margin100",
        "pass" if int(target["days_over_100pct"]) == 0 else "fail",
        float(target["days_over_100pct"]),
        "0 days",
        "broker10 保证金不应穿100%。",
    )
    add(
        "target_2x_cost_dd40",
        "pass" if float(target_cost2["max_dd_pct"]) >= -40.0 else "watch",
        float(target_cost2["max_dd_pct"]),
        ">= -40%",
        "2x成本压力不应明显失控。",
    )
    add(
        "jd_ai_selected_enough_to_be_real_test",
        "watch" if jd_selected_rate < 10.0 else "pass",
        jd_selected_rate,
        ">= 10% eval months preferred",
        "如果鸡蛋几乎进不了AI top9，本次更多是在测试top9/maxpos，不是在测试鸡蛋。",
    )
    add(
        "jd_product_pnl_positive",
        "pass" if jd_pnl > 0.0 else "watch",
        jd_pnl,
        "> 0",
        "鸡蛋自身净贡献。",
    )

    check_frame = pd.DataFrame(checks)
    hard_fail = check_frame[check_frame["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = check_frame[check_frame["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision = "official_stage372_plus_jd_ai_top9_maxpos5_rejected" if hard_fail else "official_stage372_plus_jd_ai_top9_maxpos5_watch"
    return {
        "stage": "Stage405",
        "script_stage": "Stage692",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": BASE_VARIANT,
        "maxpos5_only": MAXPOS5_VARIANT,
        "target": TARGET_VARIANT,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "added_products": [JD_PRODUCT],
            "base_product_count": inputs["base_product_count"],
            "plus_product_count": inputs["plus_product_count"],
            "max_concurrent_positions_before": 4,
            "max_concurrent_positions_after": 5,
            "ai_top_n": AI_TOP_N,
            "ai_strategy": AI_TOP9_STRATEGY,
            "ai_eligibility_eval_date_min": inputs["ai_eval_date_min"],
            "ai_eligibility_eval_date_max": inputs["ai_eval_date_max"],
            "ai_eligibility_eval_dates": inputs["ai_eval_dates"],
            "full_market_prediction_coverage_caveat": (
                "Full-market AI predictions start in 2022-01-28; earlier eval dates reuse official eligibility "
                "under the Stage692 strategy and jd.DCE is not allowed before full-market prediction coverage."
            ),
        },
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
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
            "forced_events": str(FORCED_EVENTS_PATH),
            "forced_summary": str(FORCED_SUMMARY_PATH),
            "ai_audit": str(AI_AUDIT_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
            "chart": str(CHART_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    product: pd.DataFrame,
    product_delta: pd.DataFrame,
    forced_summary: pd.DataFrame,
    ai_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage692 Official Stage372 Plus jd AI Top9 Maxpos5",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- A：当前正式版 `official_live_stage372_20w_recovery_sleeve`，`maxpos4`，正式 AI。",
        "- B：只把 `max_concurrent_positions` 从 `4` 放到 `5`，其余正式版完全不变。",
        "- C：新增 `jd.DCE`，`maxpos5`，并使用 full-market AI 月度纯 `top9` 选品；2020-2021 因 full-market 预测未覆盖，沿用正式 AI 快照且不放行鸡蛋。",
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
        "## Annual",
        "",
        _md_table(annual, max_rows=80),
        "",
        "## Product Delta",
        "",
        _md_table(product_delta, max_rows=80),
        "",
        "## Product",
        "",
        _md_table(product, max_rows=120),
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
    base_identity_map = s653.s519._product_identity_cluster_map(base_metadata)
    plus_identity_map = s653.s519._product_identity_cluster_map(plus_metadata)
    specs = [
        (_official_spec(base_identity_map), base_metadata),
        (_maxpos5_spec(base_identity_map), base_metadata),
        (_target_spec(plus_identity_map), plus_metadata),
    ]

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    spec_objects = [item[0] for item in specs]
    for spec, metadata in specs:
        print(f"[stage692] running {spec.capital.variant}", flush=True)
        daily, positions, product_margin, usage, forced_events = _run_spec(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
        product_margin_frames.append(product_margin)
        if not usage.empty:
            usage_frames.append(usage)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_margin_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = s653._forced_summary(spec_objects, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = next(item[0] for item in specs if item[0].capital.variant == variant)
        for cost_multiplier in s653.COST_MULTIPLIERS:
            row = s653._metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    official_return = float(summary.loc[summary["variant"].eq(BASE_VARIANT), "total_return_pct"].iloc[0])
    for frame in (summary, cost):
        frame["return_retention_vs_official_pct"] = (
            pd.to_numeric(frame["total_return_pct"], errors="coerce").fillna(0.0)
            / official_return
            * 100.0
        ) if official_return else 0.0

    comparison = _comparison(summary, cost)
    annual, monthly = _annual_monthly(combo_daily)
    product = _product_summary(positions_all)
    product_delta = _product_delta(product)
    _plot(combo_daily)
    decision = _decision(summary, cost, comparison, product_delta, inputs)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_DELTA_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, cost, comparison, annual, product, product_delta, forced_summary, inputs["ai_audit"], decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

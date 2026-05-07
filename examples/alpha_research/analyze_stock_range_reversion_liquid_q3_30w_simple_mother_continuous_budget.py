from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import polars as pl

import analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay as rhythm_replay
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import downside_vol
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import build_target_maps, build_tracking_dates
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    ACCOUNT_SIZE_CNY,
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    NATIVE_RESULTS_DIR,
    PREFIX as SOURCE_PREFIX,
    OUTPUT_DIR as SOURCE_DIR,
    summarize_daily_extra,
    to_float,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_simple_mother_continuous_budget_v1"

FOCUS_SCENARIOS: tuple[str, ...] = (
    "top8_gross50_ind2",
    "top5_gross50_ind2",
    "top8_gross70_ind2",
    "top5_gross70_ind2",
)

PRIMARY_SCENARIO: str = "top8_gross50_ind2"
GUARD_SCENARIO: str = "top5_gross50_ind2"
USER_MAX_DRAWDOWN_LIMIT: float = -0.20
USER_RETURN_TARGET: float = 1.00

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Volatility Managed Portfolios",
        "https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf",
    ),
    (
        "Smoothing volatility targeting",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "Volatility Targeting - Risk Management in Python",
        "https://hypercode.alexisbouchez.com/risk-management/lessons/volatility-targeting",
    ),
    (
        "Target volatility strategies",
        "https://www.pfolio.io/academy/target-volatility-strategy",
    ),
    (
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub volatility topics",
        "https://github.com/topics/volatility",
    ),
)


@dataclass(frozen=True)
class BudgetRule:
    name: str
    lookback_days: int
    repair_start: float | None
    max_scale: float
    taper_start: float
    taper_end: float
    min_scale: float
    description: str

    def scale(self, prev_return: float | None) -> float:
        if prev_return is None or prev_return != prev_return:
            return 1.0
        if self.repair_start is not None and prev_return <= self.repair_start:
            return self.max_scale
        if self.repair_start is not None and self.repair_start < prev_return < self.taper_start:
            progress = (prev_return - self.repair_start) / (self.taper_start - self.repair_start)
            return self.max_scale - progress * (self.max_scale - 1.0)
        if prev_return <= self.taper_start:
            return 1.0
        if prev_return >= self.taper_end:
            return self.min_scale
        progress = (prev_return - self.taper_start) / (self.taper_end - self.taper_start)
        return 1.0 - progress * (1.0 - self.min_scale)

    def state(self, prev_return: float | None) -> str:
        if prev_return is None or prev_return != prev_return:
            return "missing"
        if self.repair_start is not None and prev_return <= self.repair_start:
            return "repair_boost"
        if self.repair_start is not None and prev_return < self.taper_start:
            return "repair_taper"
        if prev_return <= self.taper_start:
            return "full_budget"
        if prev_return >= self.taper_end:
            return "floor_budget"
        return "hot_taper"


BUDGET_RULES: tuple[BudgetRule, ...] = (
    BudgetRule(
        name="hot60_0to10_floor70",
        lookback_days=60,
        repair_start=None,
        max_scale=1.00,
        taper_start=0.00,
        taper_end=0.10,
        min_scale=0.70,
        description="自身60日收益<=0%满预算，0%-10%线性降到70%，高于10%保持70%。",
    ),
    BudgetRule(
        name="hot60_0to10_floor50",
        lookback_days=60,
        repair_start=None,
        max_scale=1.00,
        taper_start=0.00,
        taper_end=0.10,
        min_scale=0.50,
        description="自身60日收益<=0%满预算，0%-10%线性降到50%，高于10%保持50%。",
    ),
    BudgetRule(
        name="hot80_0to12_floor70",
        lookback_days=80,
        repair_start=None,
        max_scale=1.00,
        taper_start=0.00,
        taper_end=0.12,
        min_scale=0.70,
        description="自身80日收益<=0%满预算，0%-12%线性降到70%，高于12%保持70%。",
    ),
    BudgetRule(
        name="repair60_m8_boost115_hot10_floor70",
        lookback_days=60,
        repair_start=-0.08,
        max_scale=1.15,
        taper_start=0.00,
        taper_end=0.10,
        min_scale=0.70,
        description="自身60日亏损<-8%时预算115%，-8%到0%线性降至100%，0%-10%线性降至70%。",
    ),
    BudgetRule(
        name="repair80_m10_boost110_hot12_floor75",
        lookback_days=80,
        repair_start=-0.10,
        max_scale=1.10,
        taper_start=0.00,
        taper_end=0.12,
        min_scale=0.75,
        description="自身80日亏损<-10%时预算110%，-10%到0%线性降至100%，0%-12%线性降至75%。",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def calc_prev_return(equity_history: list[float], lookback_days: int) -> float | None:
    if len(equity_history) < lookback_days + 1:
        return None
    base = equity_history[-lookback_days - 1]
    if base <= 0:
        return None
    return equity_history[-1] / base - 1.0


def annualized_sharpe(values: pd.Series | list[float] | np.ndarray) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if len(clean) < 2:
        return 0.0
    std = clean.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0
    return float(clean.mean() / std * np.sqrt(TRADING_DAYS))


def max_drawdown_from_returns(values: pd.Series | list[float] | np.ndarray) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def compound_return(values: pd.Series | list[float] | np.ndarray) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    return float((1.0 + clean).prod() - 1.0)


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 40) -> str:
    if frame.empty:
        return "\n无数据。\n"
    existing = [col for col in columns if col in frame.columns]
    if not existing:
        return "\n无匹配列。\n"
    return frame[existing].head(limit).to_markdown(index=False)


def add_pct_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[f"{col}_pct"] = out[col].map(lambda value: pct(to_float(value, float("nan"))))
    return out


def patch_replay_rule(rule: BudgetRule) -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    original_calc = rhythm_replay.calc_prev_ret60
    original_bucket = rhythm_replay.bucket_ret60
    original_scale = rhythm_replay.scale_for_rhythm

    def patched_calc(equity_history: list[float]) -> float | None:
        return calc_prev_return(equity_history, rule.lookback_days)

    def patched_bucket(value: float | None) -> str:
        state = rule.state(value)
        scale = rule.scale(value)
        if value is None or value != value:
            return f"{state}|scale={scale:.8f}"
        return f"{state}|ret={value:.8f}|scale={scale:.8f}"

    def patched_scale(_rhythm_name: str, prev_strategy_ret60_state: str) -> float:
        if "scale=" not in prev_strategy_ret60_state:
            return 1.0
        return float(prev_strategy_ret60_state.rsplit("scale=", maxsplit=1)[-1])

    rhythm_replay.calc_prev_ret60 = patched_calc
    rhythm_replay.bucket_ret60 = patched_bucket
    rhythm_replay.scale_for_rhythm = patched_scale
    return original_calc, original_bucket, original_scale


def restore_replay_rule(originals: tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]) -> None:
    rhythm_replay.calc_prev_ret60, rhythm_replay.bucket_ret60, rhythm_replay.scale_for_rhythm = originals


def read_source(name: str, try_parse_dates: bool = False) -> pl.DataFrame:
    return pl.read_csv(
        SOURCE_DIR / f"{SOURCE_PREFIX}_{name}.csv",
        try_parse_dates=try_parse_dates,
        schema_overrides={"symbol": pl.Utf8},
    )


def normalize_base_daily(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
        .with_columns(
            pl.col("scenario").alias("base_scenario"),
            pl.lit("base_rerun").alias("slow_rhythm_name"),
            pl.lit("base_rerun").alias("budget_rule_name"),
            pl.lit(None).cast(pl.Int64).alias("lookback_days"),
            pl.lit(None).cast(pl.Float64).alias("repair_start"),
            pl.lit(1.0).alias("max_scale"),
            pl.lit(None).cast(pl.Float64).alias("taper_start"),
            pl.lit(None).cast(pl.Float64).alias("taper_end"),
            pl.lit(1.0).alias("min_scale"),
            pl.lit(None).cast(pl.Float64).alias("prev_strategy_ret_60"),
            pl.lit("base").alias("prev_strategy_ret60_state"),
            pl.lit(1.0).alias("rhythm_scale"),
            pl.lit(1.0).alias("budget_scale"),
        )
        .sort(["base_scenario", "date"])
    )


def build_summary_row(
    base_scenario: str,
    rule: BudgetRule,
    orders: pl.DataFrame,
    daily: pl.DataFrame,
    target_weights: pl.DataFrame,
) -> dict[str, Any]:
    summary = rhythm_replay.lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    latest_date = daily["date"].max()
    latest = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    shape_meta = (
        target_weights.filter(pl.col("scenario") == base_scenario)
        .select(
            pl.lit(int(base_scenario.split("_")[0].replace("top", ""))).alias("shape_top_k"),
            pl.lit(float(base_scenario.split("_")[1].replace("gross", "")) / 100.0).alias(
                "shape_basket_gross_weight"
            ),
            pl.lit(int(base_scenario.split("_")[2].replace("ind", ""))).alias("shape_max_per_industry"),
        )
        .row(0, named=True)
    )
    reduced_days = daily.filter(pl.col("rhythm_scale") < 0.999999).height
    boosted_days = daily.filter(pl.col("rhythm_scale") > 1.000001).height
    floor_days = daily.filter(pl.col("rhythm_scale") <= rule.min_scale + 1e-9).height
    summary.update(
        {
            **shape_meta,
            "scenario": f"{base_scenario}_{rule.name}",
            "base_scenario": base_scenario,
            "slow_rhythm_name": rule.name,
            "budget_rule_name": rule.name,
            "budget_rule_description": rule.description,
            "lookback_days": rule.lookback_days,
            "repair_start": rule.repair_start,
            "max_scale": rule.max_scale,
            "taper_start": rule.taper_start,
            "taper_end": rule.taper_end,
            "min_scale": rule.min_scale,
            "annualized_vol_min_fee": float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS)) if len(returns) > 1 else 0.0,
            "downside_vol_min_fee": downside_vol(returns),
            "annualized_sharpe_check": annualized_sharpe(returns),
            "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
            "avg_budget_scale": to_float(daily["rhythm_scale"].mean()) if not daily.is_empty() else 1.0,
            "min_observed_budget_scale": to_float(daily["rhythm_scale"].min()) if not daily.is_empty() else 1.0,
            "max_observed_budget_scale": to_float(daily["rhythm_scale"].max()) if not daily.is_empty() else 1.0,
            "risk_reduced_days": reduced_days,
            "risk_reduced_day_ratio": reduced_days / daily.height if daily.height else 0.0,
            "boosted_days": boosted_days,
            "boosted_day_ratio": boosted_days / daily.height if daily.height else 0.0,
            "floor_budget_days": floor_days,
            "floor_budget_day_ratio": floor_days / daily.height if daily.height else 0.0,
            "latest_budget_scale": latest["rhythm_scale"],
            "latest_prev_strategy_ret": latest["prev_strategy_ret_60"],
            "latest_prev_strategy_state": latest["prev_strategy_ret60_state"],
        }
    )
    return summary


def build_base_summary(source_summary: pl.DataFrame, source_daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in source_summary.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS)).to_dicts():
        scenario = row["scenario"]
        daily = source_daily.filter(pl.col("scenario") == scenario)
        returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
        row.update(
            {
                "base_scenario": scenario,
                "slow_rhythm_name": "base_rerun",
                "budget_rule_name": "base_rerun",
                "budget_rule_description": "简单20日超跌母本，不做连续风险预算。",
                "lookback_days": None,
                "repair_start": None,
                "max_scale": 1.0,
                "taper_start": None,
                "taper_end": None,
                "min_scale": 1.0,
                "annualized_vol_min_fee": float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS)) if len(returns) > 1 else 0.0,
                "downside_vol_min_fee": downside_vol(returns),
                "annualized_sharpe_check": annualized_sharpe(returns),
                "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
                "avg_budget_scale": 1.0,
                "min_observed_budget_scale": 1.0,
                "max_observed_budget_scale": 1.0,
                "risk_reduced_days": 0,
                "risk_reduced_day_ratio": 0.0,
                "boosted_days": 0,
                "boosted_day_ratio": 0.0,
                "floor_budget_days": 0,
                "floor_budget_day_ratio": 0.0,
                "latest_budget_scale": 1.0,
                "latest_prev_strategy_ret": None,
                "latest_prev_strategy_state": "base",
            }
        )
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("slow_rhythm_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("annualized_vol_min_fee").alias("base_annualized_vol_min_fee"),
            pl.col("downside_vol_min_fee").alias("base_downside_vol_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("annualized_vol_min_fee") - pl.col("base_annualized_vol_min_fee")).alias(
                "delta_annualized_vol_min_fee"
            ),
            (pl.col("downside_vol_min_fee") - pl.col("base_downside_vol_min_fee")).alias("delta_downside_vol_min_fee"),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_annualized_vol_min_fee",
                "base_downside_vol_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
        .sort(["base_scenario", "slow_rhythm_name"])
    )


def build_yearly(daily_all: pl.DataFrame) -> pl.DataFrame:
    return (
        daily_all.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["base_scenario", "slow_rhythm_name", "scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("rhythm_scale").mean().alias("avg_budget_scale"),
            (pl.col("rhythm_scale") < 0.999999).mean().alias("risk_reduced_day_ratio"),
            (pl.col("rhythm_scale") > 1.000001).mean().alias("boosted_day_ratio"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).fill_nan(0.0).alias(
                "zero_lot_target_ratio"
            )
        )
        .sort(["base_scenario", "slow_rhythm_name", "year"])
    )


def build_yearly_delta(yearly: pl.DataFrame) -> pd.DataFrame:
    pdf = yearly.to_pandas()
    rows: list[dict[str, Any]] = []
    for base_scenario, group in pdf.groupby("base_scenario"):
        base = group[group["slow_rhythm_name"].eq("base_rerun")][
            ["year", "year_return_min_fee", "year_curve_drawdown_min_fee"]
        ].rename(
            columns={
                "year_return_min_fee": "base_year_return_min_fee",
                "year_curve_drawdown_min_fee": "base_year_curve_drawdown_min_fee",
            }
        )
        for rule_name, rule_group in group[~group["slow_rhythm_name"].eq("base_rerun")].groupby("slow_rhythm_name"):
            joined = rule_group.merge(base, on="year", how="left")
            joined["delta_year_return_min_fee"] = joined["year_return_min_fee"] - joined["base_year_return_min_fee"]
            joined["delta_year_drawdown_min_fee"] = (
                joined["year_curve_drawdown_min_fee"] - joined["base_year_curve_drawdown_min_fee"]
            )
            both = (joined["delta_year_return_min_fee"] > 0) & (joined["delta_year_drawdown_min_fee"] >= 0)
            rows.append(
                {
                    "base_scenario": base_scenario,
                    "slow_rhythm_name": rule_name,
                    "years": int(len(joined)),
                    "return_improved_years": int((joined["delta_year_return_min_fee"] > 0).sum()),
                    "drawdown_improved_years": int((joined["delta_year_drawdown_min_fee"] >= 0).sum()),
                    "return_and_drawdown_improved_years": int(both.sum()),
                    "return_and_drawdown_improved_ratio": float(both.mean()),
                    "avg_delta_year_return_min_fee": joined["delta_year_return_min_fee"].mean(),
                    "avg_delta_year_drawdown_min_fee": joined["delta_year_drawdown_min_fee"].mean(),
                    "worst_delta_year_return_min_fee": joined["delta_year_return_min_fee"].min(),
                    "worst_delta_year_drawdown_min_fee": joined["delta_year_drawdown_min_fee"].min(),
                }
            )
    return pd.DataFrame(rows).sort_values(["base_scenario", "slow_rhythm_name"]).reset_index(drop=True)


def build_drawdown_windows(daily_all: pl.DataFrame) -> pd.DataFrame:
    pdf = daily_all.to_pandas()
    pdf["date"] = pd.to_datetime(pdf["date"])
    rows: list[dict[str, Any]] = []
    for base_scenario in FOCUS_SCENARIOS:
        base = pdf[(pdf["base_scenario"].eq(base_scenario)) & (pdf["slow_rhythm_name"].eq("base_rerun"))].sort_values(
            "date"
        )
        episodes = build_episodes_from_daily(base)
        episodes = episodes[episodes["base_episode_max_drawdown"] <= -0.05].head(10)
        for _, episode in episodes.iterrows():
            start = episode["base_start_date"]
            trough = episode["base_trough_date"]
            for rule_name, group in pdf[pdf["base_scenario"].eq(base_scenario)].groupby("slow_rhythm_name"):
                segment = group[(group["date"] >= start) & (group["date"] <= trough)].sort_values("date")
                if segment.empty:
                    continue
                variant_return = compound_return(segment["strategy_daily_ret_min_fee"])
                variant_dd = max_drawdown_from_returns(segment["strategy_daily_ret_min_fee"])
                rows.append(
                    {
                        **episode.to_dict(),
                        "slow_rhythm_name": rule_name,
                        "scenario": segment["scenario"].iloc[0],
                        "variant_segment_return_min_fee": variant_return,
                        "variant_segment_drawdown_min_fee": variant_dd,
                        "delta_segment_return_min_fee": variant_return - episode["base_segment_return_min_fee"],
                        "delta_segment_drawdown_min_fee": variant_dd - episode["base_segment_drawdown_min_fee"],
                        "days_to_trough": int(len(segment)),
                        "avg_actual_gross_weight": segment["actual_gross_weight"].mean(),
                        "avg_budget_scale": segment["rhythm_scale"].mean(),
                        "risk_reduced_day_ratio": (segment["rhythm_scale"] < 0.999999).mean(),
                        "boosted_day_ratio": (segment["rhythm_scale"] > 1.000001).mean(),
                        "positive_delta_window": variant_return > episode["base_segment_return_min_fee"],
                        "drawdown_improved_window": variant_dd >= episode["base_segment_drawdown_min_fee"],
                    }
                )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["return_and_drawdown_improved_window"] = out["positive_delta_window"] & out["drawdown_improved_window"]
    out["touches_2018"] = (
        out["base_peak_date"].dt.year.eq(2018)
        | out["base_start_date"].dt.year.eq(2018)
        | out["base_trough_date"].dt.year.eq(2018)
    )
    return out.sort_values(["base_scenario", "base_episode_max_drawdown", "slow_rhythm_name"]).reset_index(drop=True)


def build_episodes_from_daily(base_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    work = base_daily.sort_values("date").reset_index(drop=True)
    if work.empty:
        return pd.DataFrame()
    peak_equity = float(work.loc[0, "equity_min_fee"])
    peak_date = work.loc[0, "date"]
    current: dict[str, Any] | None = None
    for _, row in work.iloc[1:].iterrows():
        equity = float(row["equity_min_fee"])
        current_date = row["date"]
        if equity >= peak_equity - 1e-12:
            if current is not None:
                current["base_recovery_date"] = current_date
                current["base_recovered"] = True
                rows.append(current)
                current = None
            peak_equity = equity
            peak_date = current_date
            continue
        if current is None:
            current = {
                "base_scenario": row["base_scenario"],
                "base_peak_date": peak_date,
                "base_start_date": current_date,
                "base_peak_equity": peak_equity,
                "base_trough_date": current_date,
                "base_trough_equity": equity,
                "base_recovery_date": pd.NaT,
                "base_recovered": False,
            }
        if equity < float(current["base_trough_equity"]):
            current["base_trough_date"] = current_date
            current["base_trough_equity"] = equity
    if current is not None:
        rows.append(current)
    episodes = pd.DataFrame(rows)
    if episodes.empty:
        return episodes
    enriched: list[dict[str, Any]] = []
    for row in episodes.itertuples(index=False):
        segment = work[(work["date"] >= row.base_start_date) & (work["date"] <= row.base_trough_date)]
        base_return = compound_return(segment["strategy_daily_ret_min_fee"])
        base_dd = max_drawdown_from_returns(segment["strategy_daily_ret_min_fee"])
        enriched.append(
            {
                **row._asdict(),
                "base_episode_max_drawdown": row.base_trough_equity / row.base_peak_equity - 1.0,
                "base_segment_return_min_fee": base_return,
                "base_segment_drawdown_min_fee": base_dd,
            }
        )
    return pd.DataFrame(enriched).sort_values("base_episode_max_drawdown").reset_index(drop=True)


def build_window_summary(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty:
        return pd.DataFrame()
    work = windows[~windows["slow_rhythm_name"].eq("base_rerun")].copy()
    work["non2018_major"] = ~work["touches_2018"]
    rows: list[dict[str, Any]] = []
    for (base_scenario, rule_name, bucket), group in work.groupby(
        ["base_scenario", "slow_rhythm_name", "non2018_major"]
    ):
        label = "non2018_major_windows" if bucket else "windows_touching_2018"
        both = group["return_and_drawdown_improved_window"].astype(bool)
        rows.append(
            {
                "base_scenario": base_scenario,
                "slow_rhythm_name": rule_name,
                "window_bucket": label,
                "window_count": int(len(group)),
                "return_and_drawdown_improved_windows": int(both.sum()),
                "return_and_drawdown_improved_ratio": float(both.mean()),
                "avg_delta_segment_return_min_fee": group["delta_segment_return_min_fee"].mean(),
                "avg_delta_segment_drawdown_min_fee": group["delta_segment_drawdown_min_fee"].mean(),
                "worst_delta_segment_return_min_fee": group["delta_segment_return_min_fee"].min(),
                "worst_delta_segment_drawdown_min_fee": group["delta_segment_drawdown_min_fee"].min(),
                "avg_actual_gross_weight": group["avg_actual_gross_weight"].mean(),
                "avg_budget_scale": group["avg_budget_scale"].mean(),
                "avg_risk_reduced_day_ratio": group["risk_reduced_day_ratio"].mean(),
                "avg_boosted_day_ratio": group["boosted_day_ratio"].mean(),
            }
        )
    return pd.DataFrame(rows).sort_values(["base_scenario", "slow_rhythm_name", "window_bucket"]).reset_index(drop=True)


def build_quality(summary: pd.DataFrame, yearly_delta: pd.DataFrame, window_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: str, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": str(value),
                "expected": expected,
                "note": note,
            }
        )

    stress = summary[~summary["slow_rhythm_name"].eq("base_rerun")]
    primary = stress[stress["base_scenario"].eq(PRIMARY_SCENARIO)]
    guard = stress[stress["base_scenario"].eq(GUARD_SCENARIO)]
    improve_both = stress[(stress["delta_total_return_min_fee"] > 0) & (stress["delta_max_drawdown_min_fee"] > 0)]
    primary_improve_both = primary[
        (primary["delta_total_return_min_fee"] > 0) & (primary["delta_max_drawdown_min_fee"] > 0)
    ]
    primary_within_20 = primary[primary["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT]
    high_return_within_20 = stress[
        (stress["total_return_min_fee"] >= USER_RETURN_TARGET)
        & (stress["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT)
    ]
    guard_bad = guard[(guard["delta_total_return_min_fee"] < 0) & (guard["delta_max_drawdown_min_fee"] < 0)]
    primary_year = yearly_delta[yearly_delta["base_scenario"].eq(PRIMARY_SCENARIO)]
    primary_window = window_summary[
        (window_summary["base_scenario"].eq(PRIMARY_SCENARIO))
        & (window_summary["window_bucket"].eq("non2018_major_windows"))
    ]
    best_primary_window_ratio = primary_window["return_and_drawdown_improved_ratio"].max() if not primary_window.empty else 0.0
    best_primary_year_ratio = (
        primary_year["return_and_drawdown_improved_ratio"].max() if not primary_year.empty else 0.0
    )

    add("focus_scenario_count", "pass" if summary["base_scenario"].nunique() == len(FOCUS_SCENARIOS) else "fail", summary["base_scenario"].nunique(), str(len(FOCUS_SCENARIOS)), "固定四个简单母本形状。")
    add("budget_rule_count", "pass" if stress["slow_rhythm_name"].nunique() == len(BUDGET_RULES) else "fail", stress["slow_rhythm_name"].nunique(), str(len(BUDGET_RULES)), "只运行预注册连续预算函数。")
    add("no_hard_zero_budget", "pass" if stress["min_observed_budget_scale"].min() > 0 else "fail", f"{stress['min_observed_budget_scale'].min():.4f}", ">0", "本阶段不允许硬清仓。")
    add("any_rule_improves_return_and_drawdown", "pass" if len(improve_both) > 0 else "warn", len(improve_both), ">0", "全体场景中是否存在收益和回撤同向改善。")
    add("primary_improves_return_and_drawdown", "pass" if len(primary_improve_both) > 0 else "warn", f"{len(primary_improve_both)}/{len(primary)}", ">0", "主母本top8_gross50_ind2是否同向改善。")
    add("primary_within_20pct", "pass" if len(primary_within_20) > 0 else "warn", f"{len(primary_within_20)}/{len(primary)}", ">0", "主母本是否进入20%以内回撤。")
    add("high_return_within_20pct", "pass" if len(high_return_within_20) > 0 else "warn", len(high_return_within_20), ">0", "是否出现30万高收益且20%以内回撤版本。")
    add("guard_not_both_worse", "pass" if len(guard_bad) == 0 else "warn", f"both_worse={len(guard_bad)}/{len(guard)}", "0", "top5护栏不能明显同步变差。")
    add("primary_yearly_breadth", "pass" if best_primary_year_ratio >= 0.50 else "warn", f"best_ratio={best_primary_year_ratio:.2%}", ">=50%", "主母本年度收益和回撤同向改善广度。")
    add("primary_non2018_window_relief", "pass" if best_primary_window_ratio >= 0.50 else "warn", f"best_ratio={best_primary_window_ratio:.2%}", ">=50%", "主母本非2018主要回撤窗口缓冲广度。")
    add("no_signal_change", "pass", "only exposure budget", "only exposure budget", "不改变选股、top_k、行业上限、持有期和成交约束。")
    return pd.DataFrame(rows)


def build_report(
    summary: pd.DataFrame,
    yearly_delta: pd.DataFrame,
    window_summary: pd.DataFrame,
    windows: pd.DataFrame,
    quality: pd.DataFrame,
    meta: dict[str, Any],
) -> str:
    pct_summary = add_pct_columns(
        summary,
        [
            "total_return_min_fee",
            "max_drawdown_min_fee",
            "delta_total_return_min_fee",
            "delta_max_drawdown_min_fee",
            "sharpe_min_fee",
            "avg_actual_gross_weight",
            "avg_budget_scale",
            "risk_reduced_day_ratio",
            "boosted_day_ratio",
            "zero_lot_target_ratio",
            "latest_exposure_capture_ratio",
        ],
    )
    pct_year = add_pct_columns(
        yearly_delta,
        [
            "return_and_drawdown_improved_ratio",
            "avg_delta_year_return_min_fee",
            "avg_delta_year_drawdown_min_fee",
            "worst_delta_year_return_min_fee",
            "worst_delta_year_drawdown_min_fee",
        ],
    )
    pct_window = add_pct_columns(
        window_summary,
        [
            "return_and_drawdown_improved_ratio",
            "avg_delta_segment_return_min_fee",
            "avg_delta_segment_drawdown_min_fee",
            "worst_delta_segment_return_min_fee",
            "worst_delta_segment_drawdown_min_fee",
            "avg_actual_gross_weight",
            "avg_budget_scale",
        ],
    )
    pct_windows = add_pct_columns(
        windows,
        [
            "base_episode_max_drawdown",
            "delta_segment_return_min_fee",
            "delta_segment_drawdown_min_fee",
            "avg_actual_gross_weight",
            "avg_budget_scale",
            "risk_reduced_day_ratio",
            "boosted_day_ratio",
        ],
    )
    stress = summary[~summary["slow_rhythm_name"].eq("base_rerun")].copy()
    best_return = stress.sort_values(["total_return_min_fee", "max_drawdown_min_fee"], ascending=[False, False]).iloc[0]
    best_dd = stress.sort_values(["max_drawdown_min_fee", "total_return_min_fee"], ascending=[False, False]).iloc[0]
    primary = stress[stress["base_scenario"].eq(PRIMARY_SCENARIO)]
    best_primary = primary.sort_values(["max_drawdown_min_fee", "total_return_min_fee"], ascending=[False, False]).iloc[0]
    improve_both = stress[(stress["delta_total_return_min_fee"] > 0) & (stress["delta_max_drawdown_min_fee"] > 0)]
    high_goal = stress[
        (stress["total_return_min_fee"] >= USER_RETURN_TARGET)
        & (stress["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT)
    ]
    lines = [
        "# 第336阶段：简单超跌母本连续风险预算回放",
        "",
        "## 结论摘要",
        "",
        "- 本阶段固定简单20日超跌母本，不改变选股、top_k、行业上限、持有期和成交约束。",
        "- 只对目标权重做预注册连续预算缩放，并重新通过30万整手账户回放，避免日收益乘系数带来的虚假平滑。",
        f"- 全部预算变体中，收益和回撤同向改善 `{len(improve_both)}/{len(stress)}`；高收益且20%以内回撤 `{len(high_goal)}` 个。",
        f"- 总收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`。",
        f"- 回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`。",
        f"- 主母本回撤最浅：`{best_primary['scenario']}`，总收益`{pct(best_primary['total_return_min_fee'])}`，最大回撤`{pct(best_primary['max_drawdown_min_fee'])}`。",
        "",
        "## 元信息",
        "",
        f"- 生成时间：{meta['generated_at']}",
        f"- 输入目录：`{SOURCE_DIR}`",
        f"- 输出目录：`{OUTPUT_DIR}`",
        f"- 账户规模：{ACCOUNT_SIZE_CNY:,.0f} CNY",
        f"- 用户目标：总收益≥{pct(USER_RETURN_TARGET)}，最大回撤≥{pct(USER_MAX_DRAWDOWN_LIMIT)}",
        "",
        "## 外部调研与判断",
        "",
        "- 波动目标和动态风险预算的共同经验是：组合层缩放应连续、低频、可解释，并且要把交易成本和换手纳入回放。",
        "- Smoothing volatility targeting 的启发是避免0/1切换；本阶段只设置少数平滑函数，并要求年度和非2018回撤窗口反证。",
        "- GitHub/公开Python示例多把风险预算作为overlay，而不是重写alpha；这与当前线“回到简单母本”的方向一致。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], limit=40),
        "",
        "## 总览",
        "",
        markdown_table(
            pct_summary,
            [
                "base_scenario",
                "slow_rhythm_name",
                "total_return_min_fee_pct",
                "max_drawdown_min_fee_pct",
                "delta_total_return_min_fee_pct",
                "delta_max_drawdown_min_fee_pct",
                "sharpe_min_fee",
                "avg_actual_gross_weight_pct",
                "avg_budget_scale_pct",
                "risk_reduced_day_ratio_pct",
                "boosted_day_ratio_pct",
                "zero_lot_target_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 年度广度",
        "",
        markdown_table(
            pct_year,
            [
                "base_scenario",
                "slow_rhythm_name",
                "years",
                "return_improved_years",
                "drawdown_improved_years",
                "return_and_drawdown_improved_years",
                "return_and_drawdown_improved_ratio_pct",
                "avg_delta_year_return_min_fee_pct",
                "avg_delta_year_drawdown_min_fee_pct",
                "worst_delta_year_return_min_fee_pct",
                "worst_delta_year_drawdown_min_fee_pct",
            ],
            limit=80,
        ),
        "",
        "## 回撤窗口汇总",
        "",
        markdown_table(
            pct_window,
            [
                "base_scenario",
                "slow_rhythm_name",
                "window_bucket",
                "window_count",
                "return_and_drawdown_improved_windows",
                "return_and_drawdown_improved_ratio_pct",
                "avg_delta_segment_return_min_fee_pct",
                "avg_delta_segment_drawdown_min_fee_pct",
                "worst_delta_segment_return_min_fee_pct",
                "worst_delta_segment_drawdown_min_fee_pct",
                "avg_budget_scale_pct",
            ],
            limit=120,
        ),
        "",
        "## 主母本非2018主要回撤窗口明细",
        "",
        markdown_table(
            pct_windows[
                (pct_windows["base_scenario"].eq(PRIMARY_SCENARIO))
                & (~pct_windows["touches_2018"])
                & (~pct_windows["slow_rhythm_name"].eq("base_rerun"))
            ],
            [
                "slow_rhythm_name",
                "base_start_date",
                "base_trough_date",
                "base_episode_max_drawdown_pct",
                "delta_segment_return_min_fee_pct",
                "delta_segment_drawdown_min_fee_pct",
                "avg_budget_scale_pct",
                "risk_reduced_day_ratio_pct",
                "boosted_day_ratio_pct",
            ],
            limit=80,
        ),
        "",
        "## 研究判断",
        "",
        "- 过拟合判断：低于参数扫参，但仍需警惕。规则数量少且预注册，没有改alpha；但预算状态来自样本内发现的策略热度，因此只能作为反证阶段。",
        "- 继续价值判断：若能同时改善主母本、护栏和非2018窗口，则继续；否则应放弃组合层预算，转向信号层反转失败识别。",
        "- 当前动作不触发A/B实验，不修改第78，不修改`stock_range_paper_v1`。",
        "",
        "## 输出文件",
        "",
        f"- `{PREFIX}_summary.csv`",
        f"- `{PREFIX}_yearly.csv`",
        f"- `{PREFIX}_yearly_delta.csv`",
        f"- `{PREFIX}_drawdown_windows.csv`",
        f"- `{PREFIX}_window_summary.csv`",
        f"- `{PREFIX}_quality_checkpoints.csv`",
        f"- `{PREFIX}_daily.csv`",
        f"- `{PREFIX}_orders.csv`",
        f"- `{PREFIX}_meta.json`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = read_source("summary", try_parse_dates=True)
    source_daily = read_source("daily", try_parse_dates=True)
    target_weights = read_source("target_weights", try_parse_dates=True).filter(pl.col("scenario").is_in(FOCUS_SCENARIOS))
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pl.DataFrame] = [normalize_base_daily(source_daily)]
    order_frames: list[pl.DataFrame] = []

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = target_weights.filter(pl.col("scenario") == base_scenario).drop("scenario")
        target_maps = build_target_maps(scenario_targets)
        dates = build_tracking_dates(scenario_targets, benchmark_df)
        for rule in BUDGET_RULES:
            rhythm = rhythm_replay.SlowRhythm(rule.name, rule.description)
            originals = patch_replay_rule(rule)
            try:
                orders, daily, _curves, _scaled_targets = rhythm_replay.replay_lot_account_with_slow_rhythm(
                    base_scenario,
                    rhythm,
                    target_maps,
                    dates,
                    exec_info,
                )
            finally:
                restore_replay_rule(originals)
            daily = daily.with_columns(
                pl.lit(rule.name).alias("budget_rule_name"),
                pl.lit(rule.lookback_days).alias("lookback_days"),
                pl.lit(rule.repair_start).cast(pl.Float64).alias("repair_start"),
                pl.lit(rule.max_scale).alias("max_scale"),
                pl.lit(rule.taper_start).alias("taper_start"),
                pl.lit(rule.taper_end).alias("taper_end"),
                pl.lit(rule.min_scale).alias("min_scale"),
                pl.col("rhythm_scale").alias("budget_scale"),
            )
            if not orders.is_empty():
                orders = orders.with_columns(
                    pl.lit(rule.name).alias("budget_rule_name"),
                    pl.lit(rule.lookback_days).alias("lookback_days"),
                    pl.lit(rule.repair_start).cast(pl.Float64).alias("repair_start"),
                    pl.lit(rule.max_scale).alias("max_scale"),
                    pl.lit(rule.taper_start).alias("taper_start"),
                    pl.lit(rule.taper_end).alias("taper_end"),
                    pl.lit(rule.min_scale).alias("min_scale"),
                )
                order_frames.append(orders)
            summary_rows.append(build_summary_row(base_scenario, rule, orders, daily, target_weights))
            daily_frames.append(daily)

    base_summary = build_base_summary(source_summary, source_daily)
    stress_summary = pl.DataFrame(summary_rows, infer_schema_length=None)
    summary = add_base_deltas(pl.concat([base_summary, stress_summary], how="diagonal_relaxed"))
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed").sort(["base_scenario", "slow_rhythm_name", "date"])
    orders_all = pl.concat(order_frames, how="diagonal_relaxed") if order_frames else pl.DataFrame()
    yearly = build_yearly(daily_all)
    yearly_delta = build_yearly_delta(yearly)
    windows = build_drawdown_windows(daily_all)
    window_summary = build_window_summary(windows)

    summary_pd = summary.to_pandas()
    quality = build_quality(summary_pd, yearly_delta, window_summary)
    meta: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "output_dir": str(OUTPUT_DIR),
        "prefix": PREFIX,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "focus_scenarios": list(FOCUS_SCENARIOS),
        "primary_scenario": PRIMARY_SCENARIO,
        "guard_scenario": GUARD_SCENARIO,
        "budget_rules": [rule.__dict__ for rule in BUDGET_RULES],
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
        "quality_status_counts": quality["status"].value_counts().to_dict() if not quality.empty else {},
    }

    summary.write_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv")
    yearly.write_csv(OUTPUT_DIR / f"{PREFIX}_yearly.csv")
    yearly_delta.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_delta.csv", index=False)
    windows.to_csv(OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv", index=False)
    window_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_window_summary.csv", index=False)
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False)
    daily_all.write_csv(OUTPUT_DIR / f"{PREFIX}_daily.csv")
    if not orders_all.is_empty():
        orders_all.write_csv(OUTPUT_DIR / f"{PREFIX}_orders.csv")
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(summary_pd, yearly_delta, window_summary, windows, quality, meta)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nquality:")
    print(quality.to_string(index=False))
    focus = summary_pd[
        summary_pd["base_scenario"].isin([PRIMARY_SCENARIO, "top8_gross70_ind2"])
        & ~summary_pd["slow_rhythm_name"].eq("base_rerun")
    ].sort_values(["base_scenario", "max_drawdown_min_fee", "total_return_min_fee"], ascending=[True, False, False])
    print("\nfocus:")
    print(
        focus[
            [
                "base_scenario",
                "slow_rhythm_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_budget_scale",
                "risk_reduced_day_ratio",
                "boosted_day_ratio",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

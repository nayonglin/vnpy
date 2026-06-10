from __future__ import annotations

from dataclasses import replace
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

import analyze_qmt_roll_ai_product_suitability_market_walkforward as market_ai
import analyze_qmt_roll_ai_product_suitability_walkforward as suitability
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage785_stage777_ai_on_off_2018_2019 as s785
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage786_current_ai_oos_2018_2019_v1"
OUTPUT_PREFIX = "qmt_roll_stage786_current_ai_oos_2018_2019"
LINE_ID = "futures_trend_2019_data_extension"

SOURCE_PREFIX = "qmt_roll_stage786_ai_source_floor35_2015_2019"
SOURCE_START = pd.Timestamp("2015-01-01")
SOURCE_END = pd.Timestamp("2019-12-31")
SOURCE_PRELOAD = pd.Timestamp("2014-01-01")
TEST_START = pd.Timestamp("2018-01-01")
TEST_END = pd.Timestamp("2019-12-31")
FIRST_AI_EVAL_MONTH = pd.Period("2017-12", freq="M")

AI_ON_VARIANT = "stage786_stage777_current_ai_pit_2018_2019"
AI_OFF_VARIANT = "stage786_stage777_ai_off_2018_2019"
AI_ON_PROFILE = "stage786_stage777_current_ai_pit"
AI_OFF_PROFILE = "stage786_stage777_ai_off"

SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.json"
PRODUCT_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_{MODEL_TAG}.csv"
MARKET_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
FEATURED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_featured_daily_{MODEL_TAG}.csv"
SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
AI_POOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pit_ai_pool_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_training_audit_{MODEL_TAG}.csv"
SELECTED_PRODUCTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_products_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _artifact_paths(prefix: str) -> dict[str, Path]:
    return {
        "daily": OUTPUT_DIR / f"{prefix}_daily.csv",
        "position_changes": OUTPUT_DIR / f"{prefix}_position_changes_2020_2026_04.csv",
        "entry_candidate_snapshots": OUTPUT_DIR / f"{prefix}_entry_candidate_snapshots_2020_2026_04.csv",
        "statistics": OUTPUT_DIR / f"{prefix}_statistics.json",
    }


def _csv_date_range(path: Path, date_columns: tuple[str, ...]) -> tuple[str, str, int]:
    if not path.exists():
        return "", "", 0
    df = pd.read_csv(path, usecols=lambda column: column in set(date_columns))
    dates: pd.Series | None = None
    for column in date_columns:
        if column in df.columns:
            values = pd.to_datetime(df[column], errors="coerce").dropna()
            if not values.empty:
                dates = values
                break
    if dates is None or dates.empty:
        return "", "", int(len(df))
    return (
        pd.Timestamp(dates.min()).date().isoformat(),
        pd.Timestamp(dates.max()).date().isoformat(),
        int(len(df)),
    )


def _source_ready(paths: dict[str, Path]) -> bool:
    position_path = paths["position_changes"]
    candidate_path = paths["entry_candidate_snapshots"]
    if not position_path.exists() or not candidate_path.exists():
        return False
    pos_min, pos_max, _ = _csv_date_range(position_path, ("date", "datetime"))
    cand_min, cand_max, _ = _csv_date_range(candidate_path, ("datetime", "date"))
    if not pos_min or not pos_max or not cand_min or not cand_max:
        return False
    return (
        pd.Timestamp(pos_min) <= SOURCE_START
        and pd.Timestamp(pos_max) >= SOURCE_END
        and pd.Timestamp(cand_min) <= TEST_START
        and pd.Timestamp(cand_max) >= SOURCE_END
    )


def ensure_source_artifacts() -> dict[str, Any]:
    paths = _artifact_paths(SOURCE_PREFIX)
    if _source_ready(paths):
        position_min, position_max, position_rows = _csv_date_range(paths["position_changes"], ("date", "datetime"))
        candidate_min, candidate_max, candidate_rows = _csv_date_range(paths["entry_candidate_snapshots"], ("datetime", "date"))
        summary = {
            "generated": False,
            "source_prefix": SOURCE_PREFIX,
            "analysis_start": SOURCE_START.date().isoformat(),
            "analysis_end": SOURCE_END.date().isoformat(),
            "preload_start": SOURCE_PRELOAD.date().isoformat(),
            "artifact_dates": {
                "position_min_date": position_min,
                "position_max_date": position_max,
                "position_rows": position_rows,
                "candidate_min_date": candidate_min,
                "candidate_max_date": candidate_max,
                "candidate_rows": candidate_rows,
            },
            "outputs": {key: str(path) for key, path in paths.items()},
        }
        SOURCE_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    _, _, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=CORR20_06_08_FLOOR35_OVERRIDES,
        analysis_start=SOURCE_START.to_pydatetime(),
        analysis_end=SOURCE_END.to_pydatetime(),
        preload_start=SOURCE_PRELOAD.to_pydatetime(),
        capital=200_000,
        save_artifacts=True,
        include_start_year_sweep=False,
        file_prefix=SOURCE_PREFIX,
        chart_title="Stage786 PIT AI Source Floor35 2015-2019",
    )
    position_min, position_max, position_rows = _csv_date_range(paths["position_changes"], ("date", "datetime"))
    candidate_min, candidate_max, candidate_rows = _csv_date_range(paths["entry_candidate_snapshots"], ("datetime", "date"))
    summary = {
        "generated": True,
        "source_prefix": SOURCE_PREFIX,
        "analysis_start": SOURCE_START.date().isoformat(),
        "analysis_end": SOURCE_END.date().isoformat(),
        "preload_start": SOURCE_PRELOAD.date().isoformat(),
        "statistics": build_summary_row(
            statistics,
            analysis_start=SOURCE_START.to_pydatetime(),
            analysis_end=SOURCE_END.to_pydatetime(),
            total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
            total_slippage=float(statistics.get("total_slippage", 0) or 0),
            total_commission=float(statistics.get("total_commission", 0) or 0),
        ),
        "artifact_dates": {
            "position_min_date": position_min,
            "position_max_date": position_max,
            "position_rows": position_rows,
            "candidate_min_date": candidate_min,
            "candidate_max_date": candidate_max,
            "candidate_rows": candidate_rows,
        },
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    SOURCE_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def _training_label_cutoff(daily_dates: pd.Series, eval_date: pd.Timestamp) -> pd.Timestamp:
    dates = pd.to_datetime(daily_dates).dropna().drop_duplicates().sort_values().reset_index(drop=True)
    eval_values = dates[dates <= eval_date]
    if eval_values.empty:
        raise ValueError(f"eval date {eval_date.date()} is before source dates")
    eval_index = int(eval_values.index[-1])
    cutoff_index = max(0, eval_index - int(suitability.FUTURE_HORIZON_DAYS))
    return pd.Timestamp(dates.iloc[cutoff_index]).normalize()


def _month_end_eval_dates(daily: pd.DataFrame) -> list[pd.Timestamp]:
    work = daily[["date"]].drop_duplicates().copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    work["month"] = work["date"].dt.to_period("M")
    dates = [pd.Timestamp(item).normalize() for item in work.groupby("month")["date"].max().sort_values().tolist()]
    return [
        date
        for date in dates
        if pd.Timestamp(date).to_period("M") >= FIRST_AI_EVAL_MONTH and TEST_END >= pd.Timestamp(date) >= SOURCE_START
    ]


def _build_live_rows(featured: pd.DataFrame, eval_date: pd.Timestamp) -> pd.DataFrame:
    rows = featured[pd.to_datetime(featured["date"]).dt.normalize().eq(eval_date)].copy()
    if rows.empty:
        raise RuntimeError(f"no feature rows for eval date {eval_date.date().isoformat()}")
    rows.rename(columns={"date": suitability.DATE_COLUMN}, inplace=True)
    rows = suitability.add_simple_score(rows)
    rows.sort_values("product_vt_symbol", inplace=True)
    rows.reset_index(drop=True, inplace=True)
    return rows


def build_point_in_time_ai_pool(source_paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    suitability.POSITION_CHANGES_PATH = source_paths["position_changes"]
    suitability.ENTRY_SNAPSHOTS_PATH = source_paths["entry_candidate_snapshots"]

    product_daily = suitability.build_product_daily()
    system_featured = suitability.add_rolling_features(product_daily)
    market_daily = market_ai.build_market_daily(product_daily)
    market_feature_columns = [column for column in market_daily.columns if column.startswith("market_")]
    featured = system_featured.merge(
        market_daily[["date", "product_vt_symbol", "main_contract_vt", *market_feature_columns]],
        on=["date", "product_vt_symbol"],
        how="left",
    )
    featured[market_feature_columns] = featured[market_feature_columns].fillna(0.0)
    samples, feature_columns = suitability.build_monthly_samples(featured)

    pool_rows: list[pd.DataFrame] = []
    eligibility_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    eval_dates = _month_end_eval_dates(product_daily)
    for eval_date in eval_dates:
        label_cutoff = _training_label_cutoff(product_daily["date"], eval_date)
        train_start = label_cutoff - pd.Timedelta(days=suitability.TRAIN_WINDOW_DAYS)
        train_df = samples[
            (pd.to_datetime(samples[suitability.DATE_COLUMN]).dt.normalize() >= train_start)
            & (pd.to_datetime(samples[suitability.DATE_COLUMN]).dt.normalize() <= label_cutoff)
        ].copy()
        audit: dict[str, Any] = {
            "eval_date": eval_date.date().isoformat(),
            "train_start": train_start.date().isoformat(),
            "training_label_cutoff": label_cutoff.date().isoformat(),
            "future_horizon_days": int(suitability.FUTURE_HORIZON_DAYS),
            "train_rows": int(len(train_df)),
            "train_months": int(train_df[suitability.DATE_COLUMN].nunique()) if not train_df.empty else 0,
            "feature_count": int(len(feature_columns)),
            "status": "scored",
            "skip_reason": "",
        }
        if len(train_df) < suitability.MIN_TRAIN_ROWS:
            audit.update({"status": "skipped", "skip_reason": "too_few_train_rows"})
            audit_rows.append(audit)
            continue
        if train_df[suitability.TARGET_COLUMN].nunique() < 2:
            audit.update({"status": "skipped", "skip_reason": "single_class_target"})
            audit_rows.append(audit)
            continue

        model = suitability.train_model(train_df, feature_columns)
        live_rows = _build_live_rows(featured, eval_date)
        live_rows[suitability.PROBABILITY_COLUMN] = suitability.score_model(model, live_rows, feature_columns)
        live_rows["train_start"] = train_start.date().isoformat()
        live_rows["training_label_cutoff"] = label_cutoff.date().isoformat()
        live_rows["train_rows"] = int(len(train_df))
        live_rows["train_months"] = int(train_df[suitability.DATE_COLUMN].nunique())
        ranked = live_rows.sort_values(
            [suitability.PROBABILITY_COLUMN, suitability.SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        ranked["ai_rank"] = range(1, len(ranked) + 1)
        pool_rows.append(ranked)

        selected = ranked.head(8).copy()
        for row in selected.itertuples(index=False):
            eligibility_rows.append(
                {
                    "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                    "score_type": "stage786_pit_current_ai_probability_top8",
                    "eval_date": eval_date.date().isoformat(),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, suitability.PROBABILITY_COLUMN)),
                    "score_rank": int(getattr(row, "ai_rank")),
                    "top_n": 9,
                }
            )
        selected_products = {str(row["product_vt_symbol"]) for row in eligibility_rows if row["eval_date"] == eval_date.date().isoformat()}
        if FU_PRODUCT not in selected_products:
            min_score = min(
                [float(row["score"]) for row in eligibility_rows if row["eval_date"] == eval_date.date().isoformat()],
                default=0.0,
            )
            eligibility_rows.append(
                {
                    "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                    "score_type": "stage786_pit_fixed_fu_satellite",
                    "eval_date": eval_date.date().isoformat(),
                    "product_vt_symbol": FU_PRODUCT,
                    "score": min_score - 1e-6,
                    "score_rank": 9,
                    "top_n": 9,
                }
            )
        audit["selected_products"] = ",".join(selected["product_vt_symbol"].astype(str).tolist())
        audit_rows.append(audit)

    if not pool_rows:
        raise RuntimeError("point-in-time AI pool produced no scored months")

    pool = pd.concat(pool_rows, ignore_index=True, sort=False)
    eligibility = pd.DataFrame(eligibility_rows).sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)
    audit = pd.DataFrame(audit_rows).sort_values("eval_date").reset_index(drop=True)
    selected_products = (
        eligibility.groupby("eval_date")
        .agg(
            selected_products=("product_vt_symbol", lambda values: ",".join(map(str, values))),
            selected_count=("product_vt_symbol", "size"),
        )
        .reset_index()
    )

    product_daily.to_csv(PRODUCT_DAILY_PATH, index=False, encoding="utf-8-sig")
    market_daily.to_csv(MARKET_DAILY_PATH, index=False, encoding="utf-8-sig")
    featured.to_csv(FEATURED_DAILY_PATH, index=False, encoding="utf-8-sig")
    samples.to_csv(SAMPLES_PATH, index=False, encoding="utf-8-sig")
    pool.to_csv(AI_POOL_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(AI_AUDIT_PATH, index=False, encoding="utf-8-sig")
    selected_products.to_csv(SELECTED_PRODUCTS_PATH, index=False, encoding="utf-8-sig")
    return pool, eligibility, audit


def _window_name() -> str:
    return "period_2018_2019"


def _window_label() -> str:
    return f"{TEST_START.date()} to {TEST_END.date()}"


def _stage777_ai_profile(metadata: dict[str, Any], *, ai_enabled: bool) -> dict[str, Any]:
    for profile in s772._profile_specs(metadata):
        if str(profile["profile"]) == "oi_restore_am40":
            base = profile["spec"]
            if ai_enabled:
                capital = replace(
                    base.capital,
                    variant=AI_ON_VARIANT,
                    label="Stage786 Stage777 PIT current AI 2018-2019",
                    note=(
                        "Stage777 AM41/OI0.8 path with current AI model form rebuilt point-in-time for 2018-2019. "
                        "Training keeps the 720d window and 60d target, but labels must be complete before each eval date."
                    ),
                )
                overrides = {
                    **base.overrides,
                    "enable_ai_product_pool_filter": True,
                    "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
                    "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                    "ai_product_pool_use_next_trade_date_for_entry": False,
                }
                spec = replace(base, capital=capital, overrides=overrides, profile=AI_ON_PROFILE)
                return {
                    **profile,
                    "profile": AI_ON_PROFILE,
                    "spec": spec,
                    "source_name": "stage786_stage777_current_ai_pit_2018_2019",
                    "ai_product_pool_enabled": 1,
                    "note": "Stage777 with point-in-time rebuilt current AI pool.",
                }

            capital = replace(
                base.capital,
                variant=AI_OFF_VARIANT,
                label="Stage786 Stage777 AI-off 2018-2019",
                note="Stage777 AM41/OI0.8 path with AI product-pool entry filtering disabled.",
            )
            overrides = {
                **base.overrides,
                "enable_ai_product_pool_filter": False,
                "ai_product_pool_eligibility_path": "",
                "ai_product_pool_strategy": "",
                "ai_product_pool_use_next_trade_date_for_entry": False,
            }
            spec = replace(base, capital=capital, overrides=overrides, profile=AI_OFF_PROFILE)
            return {
                **profile,
                "profile": AI_OFF_PROFILE,
                "spec": spec,
                "source_name": "stage786_stage777_ai_off_2018_2019",
                "ai_product_pool_enabled": 0,
                "note": "Stage777 fixed 2018-2019 slice with AI disabled.",
            }
    raise RuntimeError("missing oi_restore_am40 profile")


def _run_profile(
    profile: dict[str, Any],
    *,
    metadata: dict[str, Any],
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    original_end = s772.ANALYSIS_END
    try:
        s772.ANALYSIS_END = TEST_END
        frame, forced_events = s772._run_engine(
            profile=profile,
            start=TEST_START,
            metadata=metadata,
            base_c3_overrides=base_c3_overrides,
        )
    finally:
        s772.ANALYSIS_END = original_end

    spec = profile["spec"]
    row, curve, costs = s772.s748._metric_row(
        frame,
        spec=spec,
        window_name=_window_name(),
        window_label=_window_label(),
        window_group="fixed_2018_2019",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row.update(
        {
            "profile": profile["profile"],
            "source_name": profile["source_name"],
            "oi_mode": "oi_restore",
            "am_label": "am40",
            "declared_am_size": 41,
            "ai_product_pool_enabled": profile["ai_product_pool_enabled"],
            "requested_start_month": TEST_START.strftime("%Y-%m"),
            "start_month": TEST_START.strftime("%Y-%m"),
            "fixed_period": "2018-2019",
            "note": profile["note"],
        }
    )
    curve = s772._curve_common(curve)
    curve["profile"] = profile["profile"]
    curve["source_name"] = profile["source_name"]
    curve["oi_mode"] = "oi_restore"
    curve["am_label"] = "am40"
    curve["declared_am_size"] = 41
    curve["ai_product_pool_enabled"] = profile["ai_product_pool_enabled"]
    curve["requested_start_month"] = TEST_START.strftime("%Y-%m")
    curve["start_month"] = TEST_START.strftime("%Y-%m")
    curve["fixed_period"] = "2018-2019"
    for cost in costs:
        cost.update(
            {
                "profile": profile["profile"],
                "source_name": profile["source_name"],
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
                "ai_product_pool_enabled": profile["ai_product_pool_enabled"],
                "requested_start_month": TEST_START.strftime("%Y-%m"),
                "start_month": TEST_START.strftime("%Y-%m"),
                "fixed_period": "2018-2019",
            }
        )
    return row, costs, curve


def _run_backtest_ab() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(TEST_START.to_pydatetime()))
    profiles = [
        _stage777_ai_profile(metadata, ai_enabled=True),
        _stage777_ai_profile(metadata, ai_enabled=False),
    ]
    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for profile in profiles:
        print(f"[stage786] running {profile['profile']} {TEST_START.date()}->{TEST_END.date()}", flush=True)
        row, costs, curve = _run_profile(profile, metadata=metadata, base_c3_overrides=base_c3_overrides)
        rows.append(row)
        cost_rows.extend(costs)
        curves.append(curve)
    summary = pd.DataFrame(rows).sort_values("ai_product_pool_enabled", ascending=False).reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["ai_product_pool_enabled", "cost_multiplier"], ascending=[False, True]).reset_index(drop=True)
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["ai_product_pool_enabled", "date"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    on = summary[summary["ai_product_pool_enabled"].eq(1)].iloc[0]
    off = summary[summary["ai_product_pool_enabled"].eq(0)].iloc[0]
    keys = [
        ("end_equity", "end_equity_delta_ai_on_minus_off"),
        ("rebased_total_return_pct", "return_delta_pct_ai_on_minus_off"),
        ("rebased_max_dd_pct", "dd_delta_pp_ai_on_minus_off"),
        ("rebased_sharpe", "sharpe_delta_ai_on_minus_off"),
        ("total_slippage", "slippage_delta_ai_on_minus_off"),
        ("total_trade_count", "trade_count_delta_ai_on_minus_off"),
        ("nonzero_daily_win_rate_pct", "win_rate_delta_pp_ai_on_minus_off"),
        ("max_broker10_margin_to_equity_pct", "max_margin_delta_pp_ai_on_minus_off"),
        ("forced_margin_deleverage_count", "forced_count_delta_ai_on_minus_off"),
    ]
    row: dict[str, Any] = {
        "period": f"{TEST_START.date()}_to_{TEST_END.date()}",
        "ai_on_variant": on["variant"],
        "ai_off_variant": off["variant"],
    }
    for key, out_key in keys:
        on_value = float(pd.to_numeric(pd.Series([on.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
        off_value = float(pd.to_numeric(pd.Series([off.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
        row[f"ai_on_{key}"] = on_value
        row[f"ai_off_{key}"] = off_value
        row[out_key] = on_value - off_value
    row["ai_on_return_win"] = int(row["return_delta_pct_ai_on_minus_off"] > 0.0)
    row["ai_on_dd_win"] = int(row["dd_delta_pp_ai_on_minus_off"] > 0.0)
    return pd.DataFrame([row])


def _plot(curves: pd.DataFrame) -> None:
    labels = {
        AI_ON_VARIANT: "PIT current AI on",
        AI_OFF_VARIANT: "AI off",
    }
    colors = {
        AI_ON_VARIANT: "#2563eb",
        AI_OFF_VARIANT: "#dc2626",
    }
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        dates = pd.to_datetime(group["date"])
        equity = pd.to_numeric(group["account_equity"], errors="coerce").ffill()
        peak = equity.cummax()
        dd = (equity / peak.replace(0.0, np.nan) - 1.0).fillna(0.0) * 100.0
        axes[0].plot(dates, equity / 1_000_000, label=labels.get(variant, variant), color=colors.get(variant), linewidth=1.8)
        axes[1].plot(dates, dd, label=labels.get(variant, variant), color=colors.get(variant), linewidth=1.5)
    axes[0].axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    axes[0].set_title("Stage786: Stage777 with PIT current AI vs AI-off, 2018-2019")
    axes[0].set_ylabel("Account equity")
    axes[0].yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_xlabel("Date")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(
    *,
    source_summary: dict[str, Any],
    pool: pd.DataFrame,
    eligibility: pd.DataFrame,
    audit: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
) -> dict[str, Any]:
    comp = comparison.iloc[0].to_dict()
    ai_on = summary[summary["ai_product_pool_enabled"].eq(1)].iloc[0].to_dict()
    ai_off = summary[summary["ai_product_pool_enabled"].eq(0)].iloc[0].to_dict()
    scored_audit = audit[audit["status"].astype(str).eq("scored")].copy()
    selected_products = sorted(eligibility["product_vt_symbol"].astype(str).unique().tolist())
    return {
        "stage": "Stage786",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "question": "Use current AI product-selection method point-in-time to validate 2018-2019 sample-out behavior.",
        "source_summary": source_summary,
        "ai_method_fixed": {
            "feature_family": "current product suitability market_wf_v2 features",
            "model": "StandardScaler + LogisticRegression",
            "regularization_c": suitability.LOGISTIC_C,
            "train_window_days": suitability.TRAIN_WINDOW_DAYS,
            "future_horizon_days": suitability.FUTURE_HORIZON_DAYS,
            "top_n": 8,
            "fixed_satellite": FU_PRODUCT,
            "strict_pit_guard": "training rows must have 60d future labels completed before each eval_date",
        },
        "ai_coverage": {
            "scored_eval_months": int(scored_audit["eval_date"].nunique()),
            "first_scored_eval_date": str(scored_audit["eval_date"].min()) if not scored_audit.empty else "",
            "last_scored_eval_date": str(scored_audit["eval_date"].max()) if not scored_audit.empty else "",
            "pool_rows": int(len(pool)),
            "eligibility_rows": int(len(eligibility)),
            "selected_products_unique": selected_products,
        },
        "summary": {
            "ai_on": _json_safe(ai_on),
            "ai_off": _json_safe(ai_off),
            "comparison": _json_safe(comp),
        },
        "judgement": {
            "overfit_risk_now": "lower_than_backward_reuse",
            "why": (
                "No 2018-2019 result is used to tune AI features, top_n, model type or thresholds. "
                "This is a chronological replay of the frozen model form with an explicit label-completion guard."
            ),
            "continue_value": (
                "High if AI-on improves out-of-sample return/drawdown/trade filtering; otherwise the result directly limits "
                "how much trust we should place in the current AI as a universal selector."
            ),
        },
        "outputs": {
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "product_daily": str(PRODUCT_DAILY_PATH),
            "market_daily": str(MARKET_DAILY_PATH),
            "featured_daily": str(FEATURED_DAILY_PATH),
            "samples": str(SAMPLES_PATH),
            "ai_pool": str(AI_POOL_PATH),
            "eligibility": str(ELIGIBILITY_PATH),
            "ai_training_audit": str(AI_AUDIT_PATH),
            "selected_products": str(SELECTED_PRODUCTS_PATH),
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _build_report(decision: dict[str, Any], selected: pd.DataFrame, summary: pd.DataFrame, comparison: pd.DataFrame, audit: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage786 当前AI方法 2018-2019 严格时点外验证",
            "",
            "## 本次判断",
            "",
            "- 本次不是重调AI参数，而是冻结当前AI模型形态、特征族、60日标签、720日训练窗和top8+FU规则。",
            "- 为避免未来函数，训练样本必须在每个eval_date之前完成60日未来标签；这比旧离线walk-forward边界更严格。",
            "- 验证对象是Stage777 AM41/OI0.8正式研究基准，A/B只切换AI产品池是否启用。",
            "",
            "## AI月度选品",
            "",
            _md_table(selected, max_rows=30),
            "",
            "## 回测摘要",
            "",
            _md_table(
                summary[
                    [
                        "variant",
                        "ai_product_pool_enabled",
                        "end_equity",
                        "rebased_total_return_pct",
                        "rebased_max_dd_pct",
                        "rebased_sharpe",
                        "total_trade_count",
                        "total_slippage",
                    ]
                ],
                max_rows=10,
            ),
            "",
            "## A/B差值",
            "",
            _md_table(comparison, max_rows=5),
            "",
            "## 训练覆盖",
            "",
            _md_table(audit[["eval_date", "train_start", "training_label_cutoff", "train_rows", "train_months", "status", "skip_reason"]], max_rows=40),
            "",
            "## 文件",
            "",
            f"- Chart: `{CHART_PATH}`",
            f"- Eligibility: `{ELIGIBILITY_PATH}`",
            f"- Decision: `{DECISION_PATH}`",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = ensure_source_artifacts()
    source_paths = _artifact_paths(SOURCE_PREFIX)
    pool, eligibility, audit = build_point_in_time_ai_pool(source_paths)
    summary, cost, curves = _run_backtest_ab()
    comparison = _comparison(summary)
    selected = pd.read_csv(SELECTED_PRODUCTS_PATH)
    decision = _decision(
        source_summary=source_summary,
        pool=pool,
        eligibility=eligibility,
        audit=audit,
        summary=summary,
        comparison=comparison,
    )

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(decision, selected, summary, comparison, audit), encoding="utf-8")
    _plot(curves)

    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))
    print(f"chart: {CHART_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

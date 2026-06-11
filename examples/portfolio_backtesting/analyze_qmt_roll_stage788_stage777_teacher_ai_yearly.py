from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage786_current_ai_oos_2018_2019 as s786
from run_qmt_alignment_backtest import save_backtest_artifacts
from run_qmt_roll_backtest import build_summary_row, compute_round_trip_win_ratio
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage788_stage777_teacher_ai_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage788_stage777_teacher_ai_yearly"
LINE_ID = "futures_trend_2019_data_extension"

SOURCE_START = pd.Timestamp("2015-01-01")
SOURCE_END = pd.Timestamp("2026-05-29")
SOURCE_PRELOAD = pd.Timestamp("2014-01-01")
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE788_MAX_WORKERS", "4"))))

TEACHERS: tuple[str, ...] = ("am41_no_oi", "am41_oi08")

SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
AI_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_training_audit_{MODEL_TAG}.csv"
SELECTED_PRODUCTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_products_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_detail_{MODEL_TAG}.csv"
COMPARISON_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
COMPARISON_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_chart_{MODEL_TAG}.png"
EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_selected_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _teacher_prefix(teacher: str) -> str:
    return f"{OUTPUT_PREFIX}_{teacher}_source_2015_20260529"


def _teacher_label(teacher: str) -> str:
    labels = {
        "am41_no_oi": "AM41 no-AI teacher without OI risk restore",
        "am41_oi08": "AM41 no-AI teacher with OI restoring effective risk 0.40->0.80",
    }
    return labels[teacher]


def _source_artifact_paths(prefix: str) -> dict[str, Path]:
    return s786._artifact_paths(prefix)


def _source_ready(paths: dict[str, Path]) -> bool:
    position_path = paths["position_changes"]
    candidate_path = paths["entry_candidate_snapshots"]
    if not position_path.exists() or not candidate_path.exists():
        return False
    pos_min, pos_max, pos_rows = s786._csv_date_range(position_path, ("date", "datetime"))
    _cand_min, cand_max, cand_rows = s786._csv_date_range(candidate_path, ("datetime", "date"))
    return (
        bool(pos_min)
        and bool(pos_max)
        and pd.Timestamp(pos_min) <= SOURCE_START
        and pd.Timestamp(pos_max) >= SOURCE_END
        and bool(cand_max)
        and pd.Timestamp(cand_max) >= SOURCE_START
        and int(pos_rows) > 0
        and int(cand_rows) > 0
    )


def _teacher_profile(metadata: dict[str, Any], teacher: str, *, variant_suffix: str = "source") -> dict[str, Any]:
    if teacher == "am41_no_oi":
        base = s748._candidate_500k_spec(metadata)
        variant = f"stage788_{teacher}_{variant_suffix}"
        label = "Stage788 AM41 no-OI teacher"
        note = (
            "Stage748 500k risk 0.40, loss-streak and recovery sleeve disabled, AI disabled, "
            "research exact AM=41."
        )
    elif teacher == "am41_oi08":
        base = s757._candidate_spec(metadata)
        variant = f"stage788_{teacher}_{variant_suffix}"
        label = "Stage788 AM41 OI0.8 teacher"
        note = (
            "Stage757 500k risk 0.40 with tradable OI price confirmation restoring effective risk "
            "to 0.80, loss-streak and recovery sleeve disabled, AI disabled, research exact AM=41."
        )
    else:
        raise ValueError(f"unknown teacher: {teacher}")

    capital = replace(base.capital, variant=variant, label=label, note=note)
    overrides = {
        **base.overrides,
        "array_manager_size_floor": 40,
        "research_exact_array_manager_size": 41,
        "enable_ai_product_pool_filter": False,
        "ai_product_pool_eligibility_path": "",
        "ai_product_pool_strategy": "",
        "ai_product_pool_use_next_trade_date_for_entry": False,
        "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
    }
    spec = replace(base, capital=capital, overrides=overrides, profile=f"stage788_{teacher}")
    return {
        "teacher": teacher,
        "profile": f"stage788_{teacher}",
        "oi_mode": "oi_restore" if teacher == "am41_oi08" else "no_oi",
        "am_label": "am41",
        "declared_am_size": 41,
        "strategy_cls": s772.QmtRollPortfolioStrategyExactAm,
        "spec": spec,
        "note": note,
    }


def _run_source_teacher(metadata: dict[str, Any], teacher: str) -> dict[str, Any]:
    prefix = _teacher_prefix(teacher)
    paths = _source_artifact_paths(prefix)
    if _source_ready(paths):
        position_min, position_max, position_rows = s786._csv_date_range(paths["position_changes"], ("date", "datetime"))
        candidate_min, candidate_max, candidate_rows = s786._csv_date_range(paths["entry_candidate_snapshots"], ("datetime", "date"))
        stats = json.loads(paths["statistics"].read_text(encoding="utf-8")) if paths["statistics"].exists() else {}
        return {
            "teacher": teacher,
            "source_prefix": prefix,
            "generated": False,
            "position_min_date": position_min,
            "position_max_date": position_max,
            "position_rows": position_rows,
            "candidate_min_date": candidate_min,
            "candidate_max_date": candidate_max,
            "candidate_rows": candidate_rows,
            "statistics": stats,
            "outputs": {key: str(path) for key, path in paths.items()},
        }

    profile = _teacher_profile(metadata, teacher, variant_suffix="source")
    spec = profile["spec"]
    original_start = s772.s653.s517.START_DT
    original_end = s772.s653.s517.END_DT
    original_preload = s772.s653.s517.PRELOAD_START_DT
    try:
        s772.s653.s517.START_DT = SOURCE_START.to_pydatetime()
        s772.s653.s517.END_DT = SOURCE_END.to_pydatetime()
        s772.s653.s517.PRELOAD_START_DT = SOURCE_PRELOAD.to_pydatetime()

        s772.s653.s517.assert_stage196_database_sentinels()
        s772.s653.s517.s506._patch_stage506_raw_roots()
        base_c3_overrides = dict(s513._c3_overrides(SOURCE_START.to_pydatetime()))
        preload_start = max(SOURCE_PRELOAD.to_pydatetime(), SOURCE_START.to_pydatetime() - timedelta(days=365))
        _, open_map = s772.s653.s517.s506.s501._seed_proxy_maps()
        engine = s772.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s772.s653.s517.Interval.DAILY,
            start=preload_start,
            end=SOURCE_END.to_pydatetime(),
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s772._build_setting(
            metadata=metadata,
            spec=spec,
            base_c3_overrides=base_c3_overrides,
            start=SOURCE_START,
        )
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty teacher source daily: {teacher}")
        analysis_df = daily_df.copy()
        analysis_df = analysis_df.loc[
            (analysis_df.index >= SOURCE_START.date()) & (analysis_df.index <= SOURCE_END.date())
        ]
        statistics: dict[str, Any] = dict(engine.calculate_statistics(analysis_df))
        win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
        statistics["win_ratio"] = win_ratio_pct
        statistics["win_count"] = win_count
        statistics["round_trip_count"] = round_trip_count
        statistics["capital"] = spec.capital.c3_capital
        engine.daily_df = analysis_df
        save_backtest_artifacts(
            engine,
            statistics,
            file_prefix=prefix,
            chart_title=f"Stage788 {_teacher_label(teacher)} source 2015-2026",
            mapping_csv_path=Path(str(setting["mapping_csv_path"])).resolve(),
            analysis_start=SOURCE_START.to_pydatetime(),
        )
    finally:
        s772.s653.s517.START_DT = original_start
        s772.s653.s517.END_DT = original_end
        s772.s653.s517.PRELOAD_START_DT = original_preload

    position_min, position_max, position_rows = s786._csv_date_range(paths["position_changes"], ("date", "datetime"))
    candidate_min, candidate_max, candidate_rows = s786._csv_date_range(paths["entry_candidate_snapshots"], ("datetime", "date"))
    stats = json.loads(paths["statistics"].read_text(encoding="utf-8")) if paths["statistics"].exists() else {}
    return {
        "teacher": teacher,
        "source_prefix": prefix,
        "generated": True,
        "position_min_date": position_min,
        "position_max_date": position_max,
        "position_rows": position_rows,
        "candidate_min_date": candidate_min,
        "candidate_max_date": candidate_max,
        "candidate_rows": candidate_rows,
        "statistics": stats,
        "outputs": {key: str(path) for key, path in paths.items()},
    }


def _configure_s786_for_teacher(teacher: str) -> dict[str, Path]:
    prefix = _teacher_prefix(teacher)
    teacher_output_prefix = f"{OUTPUT_PREFIX}_{teacher}"
    s786.MODEL_TAG = MODEL_TAG
    s786.OUTPUT_PREFIX = teacher_output_prefix
    s786.SOURCE_PREFIX = prefix
    s786.SOURCE_START = SOURCE_START
    s786.SOURCE_END = SOURCE_END
    s786.TEST_END = SOURCE_END
    s786.FIRST_AI_EVAL_MONTH = pd.Period("2017-12", freq="M")
    s786.PRODUCT_DAILY_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_product_daily_{MODEL_TAG}.csv"
    s786.MARKET_DAILY_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_market_daily_{MODEL_TAG}.csv"
    s786.FEATURED_DAILY_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_featured_daily_{MODEL_TAG}.csv"
    s786.SAMPLES_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_samples_{MODEL_TAG}.csv"
    s786.AI_POOL_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_pit_ai_pool_{MODEL_TAG}.csv"
    s786.ELIGIBILITY_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_eligibility_{MODEL_TAG}.csv"
    s786.AI_AUDIT_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_ai_training_audit_{MODEL_TAG}.csv"
    s786.SELECTED_PRODUCTS_PATH = OUTPUT_DIR / f"{teacher_output_prefix}_selected_products_{MODEL_TAG}.csv"
    return {
        "product_daily": s786.PRODUCT_DAILY_PATH,
        "market_daily": s786.MARKET_DAILY_PATH,
        "featured_daily": s786.FEATURED_DAILY_PATH,
        "samples": s786.SAMPLES_PATH,
        "ai_pool": s786.AI_POOL_PATH,
        "eligibility": s786.ELIGIBILITY_PATH,
        "ai_training_audit": s786.AI_AUDIT_PATH,
        "selected_products": s786.SELECTED_PRODUCTS_PATH,
    }


def _build_teacher_ai_pool(teacher: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    paths = _configure_s786_for_teacher(teacher)
    source_paths = _source_artifact_paths(_teacher_prefix(teacher))
    pool, eligibility, audit = s786.build_point_in_time_ai_pool(source_paths)
    eligibility = eligibility.copy()
    eligibility["score_type"] = eligibility["score_type"].astype(str).str.replace(
        "stage786", f"stage788_{teacher}", regex=False
    )
    eligibility.to_csv(paths["eligibility"], index=False, encoding="utf-8-sig")
    selected_products = (
        eligibility.groupby("eval_date")
        .agg(
            selected_products=("product_vt_symbol", lambda values: ",".join(map(str, values))),
            selected_count=("product_vt_symbol", "size"),
        )
        .reset_index()
    )
    selected_products["teacher"] = teacher
    selected_products.to_csv(paths["selected_products"], index=False, encoding="utf-8-sig")
    pool["teacher"] = teacher
    eligibility["teacher"] = teacher
    audit["teacher"] = teacher
    return pool, eligibility, audit, paths


def _target_profile(
    metadata: dict[str, Any],
    *,
    teacher: str,
    ai_enabled: bool,
    eligibility_path: str,
) -> dict[str, Any]:
    profile = _teacher_profile(metadata, teacher, variant_suffix="ai_on" if ai_enabled else "ai_off")
    base = profile["spec"]
    variant = f"stage788_{teacher}_{'ai_on' if ai_enabled else 'ai_off'}"
    capital = replace(
        base.capital,
        variant=variant,
        label=f"Stage788 {teacher} {'AI-on' if ai_enabled else 'AI-off'} yearly",
        note=(
            f"{_teacher_label(teacher)} target replay. "
            f"AI product pool {'enabled from the same no-AI teacher PIT pool' if ai_enabled else 'disabled'}."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_ai_product_pool_filter": bool(ai_enabled),
        "ai_product_pool_eligibility_path": eligibility_path if ai_enabled else "",
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME if ai_enabled else "",
        "ai_product_pool_use_next_trade_date_for_entry": False,
    }
    spec = replace(base, capital=capital, overrides=overrides, profile=f"stage788_{teacher}_{'ai_on' if ai_enabled else 'ai_off'}")
    return {
        **profile,
        "profile": spec.profile,
        "spec": spec,
        "ai_product_pool_enabled": int(ai_enabled),
        "source_name": f"stage788_{teacher}_{'ai_on' if ai_enabled else 'ai_off'}",
        "note": capital.note,
    }


def _window_name(start: pd.Timestamp) -> str:
    return f"ystart_{start.strftime('%Y')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {SOURCE_END.strftime('%Y-%m-%d')}"


def _run_target_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    start = pd.Timestamp(task["start"])
    teacher = str(task["teacher"])
    profile = _target_profile(
        metadata,
        teacher=teacher,
        ai_enabled=bool(task["ai_enabled"]),
        eligibility_path=str(task["eligibility_path"]),
    )
    original_end = s772.ANALYSIS_END
    try:
        s772.ANALYSIS_END = SOURCE_END
        frame, forced_events = s772._run_engine(
            profile=profile,
            start=start,
            metadata=metadata,
            base_c3_overrides=dict(task["base_c3_overrides"]),
        )
    finally:
        s772.ANALYSIS_END = original_end

    spec = profile["spec"]
    row, curve, costs = s748._metric_row(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="year_start",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row.update(
        {
            "teacher": teacher,
            "profile": profile["profile"],
            "source_name": profile["source_name"],
            "oi_mode": profile["oi_mode"],
            "am_label": "am41",
            "declared_am_size": 41,
            "ai_product_pool_enabled": int(task["ai_enabled"]),
            "requested_start_month": start.strftime("%Y-%m"),
            "start_month": start.strftime("%Y-%m"),
            "note": profile["note"],
        }
    )
    curve = s772._curve_common(curve)
    curve["teacher"] = teacher
    curve["profile"] = profile["profile"]
    curve["source_name"] = profile["source_name"]
    curve["oi_mode"] = profile["oi_mode"]
    curve["am_label"] = "am41"
    curve["declared_am_size"] = 41
    curve["ai_product_pool_enabled"] = int(task["ai_enabled"])
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        cost.update(
            {
                "teacher": teacher,
                "profile": profile["profile"],
                "source_name": profile["source_name"],
                "oi_mode": profile["oi_mode"],
                "am_label": "am41",
                "declared_am_size": 41,
                "ai_product_pool_enabled": int(task["ai_enabled"]),
                "requested_start_month": start.strftime("%Y-%m"),
                "start_month": start.strftime("%Y-%m"),
                "variant": spec.capital.variant,
            }
        )
    return row, costs, curve


def _run_yearly_targets(eligibility_paths: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(YEAR_STARTS[0].to_pydatetime()))
    tasks: list[dict[str, Any]] = []
    for teacher in TEACHERS:
        for start in YEAR_STARTS:
            for ai_enabled in (True, False):
                tasks.append(
                    {
                        "teacher": teacher,
                        "start": start.strftime("%Y-%m-%d"),
                        "ai_enabled": ai_enabled,
                        "eligibility_path": str(eligibility_paths[teacher]),
                        "base_c3_overrides": base_c3_overrides,
                    }
                )

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage788] launching {len(tasks)} yearly target runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage788] running {idx}/{len(tasks)} {task['teacher']} {task['start']} ai={task['ai_enabled']}", flush=True)
            row, costs, curve = _run_target_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_target_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage788] completed {idx}/{len(tasks)} {task['teacher']} {task['start']} ai={task['ai_enabled']}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["teacher", "start_month", "ai_product_pool_enabled"], ascending=[True, True, False])
        .reset_index(drop=True)
    )
    cost = pd.DataFrame(cost_rows).sort_values(["teacher", "start_month", "ai_product_pool_enabled", "cost_multiplier"]).reset_index(drop=True)
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["teacher", "start_month", "ai_product_pool_enabled", "date"], ascending=[True, True, False, True])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _comparison(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for (teacher, start_month), group in summary.groupby(["teacher", "start_month"], sort=True):
        on = group[group["ai_product_pool_enabled"].eq(1)]
        off = group[group["ai_product_pool_enabled"].eq(0)]
        if on.empty or off.empty:
            continue
        on_row = on.iloc[0]
        off_row = off.iloc[0]
        row: dict[str, Any] = {
            "teacher": teacher,
            "start_month": start_month,
            "ai_on_variant": on_row["variant"],
            "ai_off_variant": off_row["variant"],
            "mature_252d": int(on_row.get("mature_252d", 0)),
        }
        for key, out_key in [
            ("end_equity", "end_equity_delta"),
            ("rebased_total_return_pct", "return_delta_pct"),
            ("rebased_max_dd_pct", "dd_delta_pp"),
            ("rebased_sharpe", "sharpe_delta"),
            ("total_slippage", "slippage_delta"),
            ("total_trade_count", "trade_count_delta"),
            ("nonzero_daily_win_rate_pct", "win_rate_delta_pp"),
            ("max_broker10_margin_to_equity_pct", "max_margin_delta_pp"),
            ("forced_margin_deleverage_count", "forced_count_delta"),
        ]:
            on_value = float(pd.to_numeric(pd.Series([on_row.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
            off_value = float(pd.to_numeric(pd.Series([off_row.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
            row[f"ai_on_{key}"] = on_value
            row[f"ai_off_{key}"] = off_value
            row[out_key] = on_value - off_value
        row["ai_return_win"] = int(row["return_delta_pct"] > 0.0)
        row["ai_dd_win"] = int(row["dd_delta_pp"] > 0.0)
        row["ai_both_win"] = int(row["ai_return_win"] and row["ai_dd_win"])
        rows.append(row)
    detail = pd.DataFrame(rows).sort_values(["teacher", "start_month"]).reset_index(drop=True)

    agg_rows: list[dict[str, Any]] = []
    for (teacher, bucket), frame in [
        (teacher_bucket, group)
        for teacher in TEACHERS
        for teacher_bucket, group in [
            ((teacher, "all"), detail[detail["teacher"].eq(teacher)]),
            ((teacher, "mature_252d"), detail[detail["teacher"].eq(teacher) & detail["mature_252d"].eq(1)]),
        ]
    ]:
        agg_rows.append(
            {
                "teacher": teacher,
                "bucket": bucket,
                "start_count": int(len(frame)),
                "return_win_count": int(frame["ai_return_win"].sum()) if len(frame) else 0,
                "return_win_rate_pct": float(frame["ai_return_win"].mean() * 100.0) if len(frame) else 0.0,
                "dd_win_count": int(frame["ai_dd_win"].sum()) if len(frame) else 0,
                "dd_win_rate_pct": float(frame["ai_dd_win"].mean() * 100.0) if len(frame) else 0.0,
                "both_win_count": int(frame["ai_both_win"].sum()) if len(frame) else 0,
                "median_return_delta_pct": float(frame["return_delta_pct"].median()) if len(frame) else 0.0,
                "p10_return_delta_pct": float(frame["return_delta_pct"].quantile(0.10)) if len(frame) else 0.0,
                "min_return_delta_pct": float(frame["return_delta_pct"].min()) if len(frame) else 0.0,
                "median_dd_delta_pp": float(frame["dd_delta_pp"].median()) if len(frame) else 0.0,
                "worst_dd_delta_pp": float(frame["dd_delta_pp"].min()) if len(frame) else 0.0,
                "median_sharpe_delta": float(frame["sharpe_delta"].median()) if len(frame) else 0.0,
                "median_trade_count_delta": float(frame["trade_count_delta"].median()) if len(frame) else 0.0,
            }
        )
    agg = pd.DataFrame(agg_rows)
    return detail, agg


def _plot_comparison(detail: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex="col")
    colors = {1: "#2563eb", 0: "#dc2626"}
    for col, teacher in enumerate(TEACHERS):
        frame = detail[detail["teacher"].eq(teacher)].copy()
        years = pd.to_datetime(frame["start_month"] + "-01").dt.year.astype(str)
        x = np.arange(len(frame))
        width = 0.36
        axes[0, col].bar(x - width / 2, frame["ai_on_rebased_total_return_pct"], width, label="AI on", color=colors[1])
        axes[0, col].bar(x + width / 2, frame["ai_off_rebased_total_return_pct"], width, label="AI off", color=colors[0])
        axes[0, col].set_title(f"{teacher}: yearly return")
        axes[0, col].set_ylabel("Return %")
        axes[0, col].grid(axis="y", alpha=0.25)
        axes[0, col].legend(loc="upper right")
        axes[1, col].bar(x - width / 2, frame["ai_on_rebased_max_dd_pct"], width, label="AI on", color=colors[1])
        axes[1, col].bar(x + width / 2, frame["ai_off_rebased_max_dd_pct"], width, label="AI off", color=colors[0])
        axes[1, col].axhline(-40.0, color="#111827", linestyle="--", linewidth=1.0)
        axes[1, col].set_title(f"{teacher}: max drawdown")
        axes[1, col].set_ylabel("Max DD %")
        axes[1, col].set_xticks(x)
        axes[1, col].set_xticklabels(years)
        axes[1, col].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COMPARISON_CHART_PATH, dpi=180)
    plt.close(fig)


def _plot_selected_equity(curves: pd.DataFrame) -> None:
    selected = curves[curves["start_month"].isin(["2018-01", "2020-01", "2022-01", "2024-01"])].copy()
    if selected.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(16, 11), sharex=True)
    styles = {1: "-", 0: "--"}
    colors = {
        "am41_no_oi": "#2563eb",
        "am41_oi08": "#059669",
    }
    for (teacher, ai_enabled, start_month), group in selected.groupby(["teacher", "ai_product_pool_enabled", "start_month"], sort=True):
        group = group.sort_values("date")
        label = f"{teacher} {'AI' if int(ai_enabled) else 'off'} {start_month}"
        axes[0].plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            color=colors.get(str(teacher), "#111827"),
            linestyle=styles[int(ai_enabled)],
            linewidth=1.5,
            alpha=0.75,
            label=label,
        )
        equity = pd.to_numeric(group["account_equity"], errors="coerce").ffill()
        dd = (equity / equity.cummax().replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
        axes[1].plot(
            pd.to_datetime(group["date"]),
            dd,
            color=colors.get(str(teacher), "#111827"),
            linestyle=styles[int(ai_enabled)],
            linewidth=1.2,
            alpha=0.75,
        )
    axes[0].axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    axes[0].set_title("Stage788 selected yearly-start equity curves")
    axes[0].set_ylabel("Account equity")
    axes[0].yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_xlabel("Date")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(EQUITY_CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(
    source_summary: pd.DataFrame,
    audit: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    comparison_agg: pd.DataFrame,
) -> dict[str, Any]:
    teacher_decisions: dict[str, Any] = {}
    for teacher in TEACHERS:
        agg = comparison_agg[(comparison_agg["teacher"].eq(teacher)) & (comparison_agg["bucket"].eq("mature_252d"))]
        scored = audit[(audit["teacher"].eq(teacher)) & (audit["status"].astype(str).eq("scored"))]
        teacher_summary = summary[summary["teacher"].eq(teacher)]
        ai_on = teacher_summary[teacher_summary["ai_product_pool_enabled"].eq(1)]
        hard_fail: list[str] = []
        watch: list[str] = []
        if agg.empty:
            hard_fail.append("missing_comparison")
        else:
            row = agg.iloc[0]
            if float(row["return_win_rate_pct"]) < 50.0:
                watch.append("ai_return_win_rate_below_50pct")
            if float(row["median_return_delta_pct"]) < 0.0:
                watch.append("ai_median_return_delta_negative")
            if float(row["median_dd_delta_pp"]) < 0.0:
                watch.append("ai_median_dd_worse")
            if int(row["both_win_count"]) == 0:
                watch.append("no_start_year_both_return_and_dd_win")
        if ai_on.empty:
            hard_fail.append("missing_ai_on_backtest")
        else:
            dds = pd.to_numeric(ai_on["rebased_max_dd_pct"], errors="coerce")
            if int((dds < -50.0).sum()) > 0:
                hard_fail.append("ai_on_dd50_fail_exists")
        teacher_decisions[teacher] = {
            "scored_eval_months": int(scored["eval_date"].nunique()) if not scored.empty else 0,
            "first_scored_eval_date": str(scored["eval_date"].min()) if not scored.empty else "",
            "last_scored_eval_date": str(scored["eval_date"].max()) if not scored.empty else "",
            "unique_selected_products": sorted(selected[selected["teacher"].eq(teacher)]["selected_products"].astype(str).tolist())[:5],
            "hard_fail": hard_fail,
            "watch": watch,
            "decision": "not_promoted" if hard_fail or watch else "candidate_needs_monthly_validation",
        }
    decision = {
        "stage": "Stage788",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hypothesis": (
            "Rebuild AI product selection from no-AI AM41 target-strategy teachers. The teacher must not use the old AI pool; "
            "monthly labels are generated point-in-time with completed 60d future labels only."
        ),
        "source_period": {
            "source_start": SOURCE_START.date().isoformat(),
            "source_end": SOURCE_END.date().isoformat(),
            "source_preload": SOURCE_PRELOAD.date().isoformat(),
        },
        "teacher_summary": _json_safe(source_summary.to_dict("records")),
        "comparison_aggregate": _json_safe(comparison_agg.to_dict("records")),
        "teacher_decisions": teacher_decisions,
        "overall_decision": "teacher_ai_yearly_screen_complete_not_formal_promotion",
        "outputs": {
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "ai_training_audit": str(AI_AUDIT_PATH),
            "selected_products": str(SELECTED_PRODUCTS_PATH),
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "comparison_detail": str(COMPARISON_DETAIL_PATH),
            "comparison_aggregate": str(COMPARISON_AGG_PATH),
            "comparison_chart": str(COMPARISON_CHART_PATH),
            "equity_chart": str(EQUITY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "overfit_reflection": (
            "Medium. AM41 and OI came from prior research, so this is not a clean greenfield feature. "
            "Risk is controlled by predeclaring two teachers, keeping model form/top8/fu satellite fixed, and using yearly starts before any monthly escalation."
        ),
        "continue_value": (
            "Yes if at least one teacher shows stable yearly AI benefit without DD50 failure; otherwise continue only as AI attribution, not promotion."
        ),
    }
    return decision


def _write_report(
    source_summary: pd.DataFrame,
    audit: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    comparison_agg: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    audit_display = audit[
        ["teacher", "eval_date", "train_start", "training_label_cutoff", "train_rows", "train_months", "status", "skip_reason"]
    ].tail(40)
    summary_display = summary[
        [
            "teacher",
            "start_month",
            "ai_product_pool_enabled",
            "end_equity",
            "rebased_total_return_pct",
            "rebased_max_dd_pct",
            "rebased_sharpe",
            "total_trade_count",
            "total_slippage",
        ]
    ]
    detail_display = comparison[
        [
            "teacher",
            "start_month",
            "return_delta_pct",
            "dd_delta_pp",
            "sharpe_delta",
            "trade_count_delta",
            "ai_return_win",
            "ai_dd_win",
        ]
    ]
    lines = [
        "# Stage788 Stage777-family 新老师 PIT AI 年度首筛",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源策略区间：`{SOURCE_START.date()}` 到 `{SOURCE_END.date()}`；年度起点：`{YEAR_STARTS[0].strftime('%Y-%m')}` 到 `{YEAR_STARTS[-1].strftime('%Y-%m')}`。",
        "- 老师共同约束：AI关闭、AM=41、连败缩放关闭、recovery sleeve关闭；只比较无OI老师与OI0.8老师。",
        "- 学生回测：同一目标策略分别打开/关闭新生成的 PIT AI eligibility。",
        "",
        "## Source Summary",
        "",
        _md_table(source_summary, max_rows=10),
        "",
        "## AI Coverage",
        "",
        _md_table(audit_display, max_rows=40),
        "",
        "## Yearly Summary",
        "",
        _md_table(summary_display, max_rows=40),
        "",
        "## AI On - AI Off Detail",
        "",
        _md_table(detail_display, max_rows=40),
        "",
        "## Aggregate",
        "",
        _md_table(comparison_agg, max_rows=20),
        "",
        "## Charts",
        "",
        f"![comparison]({COMPARISON_CHART_PATH})",
        "",
        f"![selected equity]({EQUITY_CHART_PATH})",
        "",
        "## Decision",
        "",
        f"- overall：`{decision['overall_decision']}`",
        f"- teacher_decisions：`{json.dumps(decision['teacher_decisions'], ensure_ascii=False)}`",
        f"- 过拟合判断：{decision['overfit_reflection']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    source_rows = []
    pools = []
    eligibilities = []
    audits = []
    selected_frames = []
    eligibility_paths: dict[str, Path] = {}

    for teacher in TEACHERS:
        print(f"[stage788] ensuring teacher source {teacher}", flush=True)
        source_rows.append(_run_source_teacher(metadata, teacher))
        print(f"[stage788] building PIT AI pool {teacher}", flush=True)
        pool, eligibility, audit, paths = _build_teacher_ai_pool(teacher)
        pools.append(pool)
        eligibilities.append(eligibility)
        audits.append(audit)
        selected = pd.read_csv(paths["selected_products"], encoding="utf-8-sig")
        selected_frames.append(selected)
        eligibility_paths[teacher] = paths["eligibility"]

    source_summary = pd.DataFrame(source_rows)
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    audit_all = pd.concat(audits, ignore_index=True, sort=False)
    audit_all.to_csv(AI_AUDIT_PATH, index=False, encoding="utf-8-sig")
    selected_all = pd.concat(selected_frames, ignore_index=True, sort=False)
    selected_all.to_csv(SELECTED_PRODUCTS_PATH, index=False, encoding="utf-8-sig")

    summary, cost, curves = _run_yearly_targets(eligibility_paths)
    comparison, comparison_agg = _comparison(summary)
    decision = _decision(source_summary, audit_all, selected_all, summary, comparison, comparison_agg)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_DETAIL_PATH, index=False, encoding="utf-8-sig")
    comparison_agg.to_csv(COMPARISON_AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_comparison(comparison)
    _plot_selected_equity(curves)
    _write_report(source_summary, audit_all, selected_all, summary, comparison, comparison_agg, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")
    print(f"chart: {COMPARISON_CHART_PATH}")


if __name__ == "__main__":
    main()

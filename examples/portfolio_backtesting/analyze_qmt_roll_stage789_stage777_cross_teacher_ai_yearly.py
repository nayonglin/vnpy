from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
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
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage788_stage777_teacher_ai_yearly as s788
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage789_stage777_cross_teacher_ai_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage789_stage777_cross_teacher_ai_yearly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE789_MAX_WORKERS", "4"))))

POOL_VARIANTS: tuple[str, ...] = ("ai_off", "ai_pool_am41_no_oi_teacher", "ai_pool_am41_oi08_teacher")
TEACHER_BY_POOL = {
    "ai_pool_am41_no_oi_teacher": "am41_no_oi",
    "ai_pool_am41_oi08_teacher": "am41_oi08",
}

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


def _window_name(start: pd.Timestamp) -> str:
    return f"ystart_{start.strftime('%Y')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _pool_label(pool_name: str) -> str:
    labels = {
        "ai_off": "Stage777 AI-off",
        "ai_pool_am41_no_oi_teacher": "Stage777 + AI pool from AM41 no-OI teacher",
        "ai_pool_am41_oi08_teacher": "Stage777 + AI pool from AM41 OI0.8 teacher",
    }
    return labels[pool_name]


def _eligibility_paths(metadata: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for teacher in s788.TEACHERS:
        expected = OUTPUT_DIR / f"{s788.OUTPUT_PREFIX}_{teacher}_eligibility_{s788.MODEL_TAG}.csv"
        if not expected.exists():
            s788._run_source_teacher(metadata, teacher)
            _pool, _eligibility, _audit, built_paths = s788._build_teacher_ai_pool(teacher)
            expected = built_paths["eligibility"]
        paths[teacher] = expected
    return paths


def _stage777_base_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    for profile in s772._profile_specs(metadata):
        if profile["profile"] == "oi_restore_am40":
            return profile
    raise RuntimeError("missing Stage777 base profile oi_restore_am40")


def _target_profile(
    metadata: dict[str, Any],
    *,
    pool_name: str,
    eligibility_path: str,
) -> dict[str, Any]:
    base_profile = _stage777_base_profile(metadata)
    base_spec = base_profile["spec"]
    ai_enabled = pool_name != "ai_off"
    variant = f"stage789_stage777_{pool_name}"
    note = (
        "Stage777 target fixed: 500k, AM41, OI confirmation restores effective risk 0.40->0.80, "
        "loss-streak and recovery sleeve disabled. "
        + (
            "AI product pool disabled."
            if not ai_enabled
            else f"AI product pool comes from Stage788 teacher {TEACHER_BY_POOL[pool_name]}."
        )
    )
    capital = replace(
        base_spec.capital,
        variant=variant,
        label=_pool_label(pool_name),
        note=note,
    )
    overrides = {
        **base_spec.overrides,
        "enable_ai_product_pool_filter": bool(ai_enabled),
        "ai_product_pool_eligibility_path": eligibility_path if ai_enabled else "",
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME if ai_enabled else "",
        "ai_product_pool_use_next_trade_date_for_entry": False,
    }
    spec = replace(base_spec, capital=capital, overrides=overrides, profile=variant)
    return {
        **base_profile,
        "profile": spec.profile,
        "pool_name": pool_name,
        "teacher": TEACHER_BY_POOL.get(pool_name, "none"),
        "ai_product_pool_enabled": int(ai_enabled),
        "spec": spec,
        "note": note,
    }


def _run_target_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    start = pd.Timestamp(task["start"])
    pool_name = str(task["pool_name"])
    profile = _target_profile(
        metadata,
        pool_name=pool_name,
        eligibility_path=str(task.get("eligibility_path") or ""),
    )
    original_end = s772.ANALYSIS_END
    try:
        s772.ANALYSIS_END = ANALYSIS_END
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
            "source_name": "stage789_stage777_cross_teacher_ai_yearly",
            "pool_name": pool_name,
            "teacher": profile["teacher"],
            "profile": profile["profile"],
            "oi_mode": "oi_restore",
            "am_label": "am41",
            "declared_am_size": 41,
            "ai_product_pool_enabled": profile["ai_product_pool_enabled"],
            "requested_start_month": start.strftime("%Y-%m"),
            "start_month": start.strftime("%Y-%m"),
            "note": profile["note"],
        }
    )
    curve = s772._curve_common(curve)
    curve["source_name"] = "stage789_stage777_cross_teacher_ai_yearly"
    curve["pool_name"] = pool_name
    curve["teacher"] = profile["teacher"]
    curve["profile"] = profile["profile"]
    curve["oi_mode"] = "oi_restore"
    curve["am_label"] = "am41"
    curve["declared_am_size"] = 41
    curve["ai_product_pool_enabled"] = profile["ai_product_pool_enabled"]
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        cost.update(
            {
                "source_name": "stage789_stage777_cross_teacher_ai_yearly",
                "pool_name": pool_name,
                "teacher": profile["teacher"],
                "profile": profile["profile"],
                "oi_mode": "oi_restore",
                "am_label": "am41",
                "declared_am_size": 41,
                "ai_product_pool_enabled": profile["ai_product_pool_enabled"],
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
    for start in YEAR_STARTS:
        tasks.append(
            {
                "pool_name": "ai_off",
                "start": start.strftime("%Y-%m-%d"),
                "eligibility_path": "",
                "base_c3_overrides": base_c3_overrides,
            }
        )
        for pool_name, teacher in TEACHER_BY_POOL.items():
            tasks.append(
                {
                    "pool_name": pool_name,
                    "start": start.strftime("%Y-%m-%d"),
                    "eligibility_path": str(eligibility_paths[teacher]),
                    "base_c3_overrides": base_c3_overrides,
                }
            )

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage789] launching {len(tasks)} Stage777 yearly target runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage789] running {idx}/{len(tasks)} {task['pool_name']} {task['start']}", flush=True)
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
                print(f"[stage789] completed {idx}/{len(tasks)} {task['pool_name']} {task['start']}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["start_month", "pool_name"])
        .reset_index(drop=True)
    )
    cost = (
        pd.DataFrame(cost_rows)
        .sort_values(["start_month", "pool_name", "cost_multiplier"])
        .reset_index(drop=True)
    )
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["start_month", "pool_name", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _comparison(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for start_month, group in summary.groupby("start_month", sort=True):
        off = group[group["pool_name"].eq("ai_off")]
        if off.empty:
            continue
        off_row = off.iloc[0]
        for pool_name in TEACHER_BY_POOL:
            on = group[group["pool_name"].eq(pool_name)]
            if on.empty:
                continue
            on_row = on.iloc[0]
            row: dict[str, Any] = {
                "pool_name": pool_name,
                "teacher": TEACHER_BY_POOL[pool_name],
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
    detail = pd.DataFrame(rows).sort_values(["pool_name", "start_month"]).reset_index(drop=True)

    agg_rows: list[dict[str, Any]] = []
    for pool_name in TEACHER_BY_POOL:
        pool_detail = detail[detail["pool_name"].eq(pool_name)]
        for bucket, frame in [("all", pool_detail), ("mature_252d", pool_detail[pool_detail["mature_252d"].eq(1)])]:
            dds_on = pd.to_numeric(frame.get("ai_on_rebased_max_dd_pct", pd.Series(dtype=float)), errors="coerce")
            agg_rows.append(
                {
                    "pool_name": pool_name,
                    "teacher": TEACHER_BY_POOL[pool_name],
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
                    "ai_on_dd50_fail_count": int(dds_on.lt(-50.0).sum()) if len(frame) else 0,
                }
            )
    agg = pd.DataFrame(agg_rows)
    return detail, agg


def _plot_comparison(detail: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    years = sorted(detail["start_month"].unique())
    x = np.arange(len(years))
    width = 0.34
    colors = {
        "ai_pool_am41_no_oi_teacher": "#2563eb",
        "ai_pool_am41_oi08_teacher": "#059669",
    }
    offsets = {
        "ai_pool_am41_no_oi_teacher": -width / 2,
        "ai_pool_am41_oi08_teacher": width / 2,
    }
    for pool_name, group in detail.groupby("pool_name", sort=True):
        group = group.set_index("start_month").reindex(years).reset_index()
        axes[0].bar(x + offsets[pool_name], group["return_delta_pct"], width, color=colors[pool_name], label=pool_name)
        axes[1].bar(x + offsets[pool_name], group["dd_delta_pp"], width, color=colors[pool_name], label=pool_name)
    axes[0].axhline(0.0, color="#111827", linewidth=1)
    axes[0].set_title("Stage789: Stage777 target AI-on return delta vs AI-off")
    axes[0].set_ylabel("Return delta pp")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(fontsize=8)
    axes[1].axhline(0.0, color="#111827", linewidth=1)
    axes[1].set_title("Stage789: Stage777 target AI-on drawdown delta vs AI-off")
    axes[1].set_ylabel("DD delta pp (higher is better)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([pd.Timestamp(item + "-01").year for item in years])
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(COMPARISON_CHART_PATH, dpi=180)
    plt.close(fig)


def _plot_selected_equity(curves: pd.DataFrame) -> None:
    selected = curves[curves["start_month"].isin(["2018-01", "2020-01", "2022-01", "2024-01"])].copy()
    if selected.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(16, 11), sharex=True)
    colors = {
        "ai_off": "#dc2626",
        "ai_pool_am41_no_oi_teacher": "#2563eb",
        "ai_pool_am41_oi08_teacher": "#059669",
    }
    styles = {
        "2018-01": "-",
        "2020-01": "--",
        "2022-01": "-.",
        "2024-01": ":",
    }
    for (pool_name, start_month), group in selected.groupby(["pool_name", "start_month"], sort=True):
        group = group.sort_values("date")
        label = f"{pool_name} {start_month}"
        axes[0].plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            color=colors.get(pool_name, "#111827"),
            linestyle=styles.get(start_month, "-"),
            linewidth=1.5,
            alpha=0.75,
            label=label,
        )
        equity = pd.to_numeric(group["account_equity"], errors="coerce").ffill()
        dd = (equity / equity.cummax().replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
        axes[1].plot(
            pd.to_datetime(group["date"]),
            dd,
            color=colors.get(pool_name, "#111827"),
            linestyle=styles.get(start_month, "-"),
            linewidth=1.2,
            alpha=0.75,
        )
    axes[0].axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    axes[0].set_title("Stage789 selected Stage777 yearly-start equity curves")
    axes[0].set_ylabel("Account equity")
    axes[0].yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=7)
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_xlabel("Date")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(EQUITY_CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    pool_decisions: dict[str, Any] = {}
    for pool_name in TEACHER_BY_POOL:
        mature = aggregate[aggregate["pool_name"].eq(pool_name) & aggregate["bucket"].eq("mature_252d")]
        watch: list[str] = []
        hard_fail: list[str] = []
        if mature.empty:
            hard_fail.append("missing_mature_comparison")
        else:
            row = mature.iloc[0]
            if float(row["return_win_rate_pct"]) < 50.0:
                watch.append("return_win_rate_below_50pct")
            if float(row["median_return_delta_pct"]) <= 0.0:
                watch.append("median_return_delta_not_positive")
            if float(row["median_dd_delta_pp"]) < 0.0:
                watch.append("median_drawdown_worse")
            if int(row["ai_on_dd50_fail_count"]) > 0:
                hard_fail.append("ai_on_dd50_fail_exists")
        pool_decisions[pool_name] = {
            "teacher": TEACHER_BY_POOL[pool_name],
            "hard_fail": hard_fail,
            "watch": watch,
            "decision": "not_promoted" if hard_fail or watch else "candidate_needs_monthly_validation",
        }
    return {
        "stage": "Stage789",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hypothesis": (
            "Apply the two Stage788 point-in-time AI product pools to the same Stage777 target strategy. "
            "This tests whether the teacher pools are useful as a Stage777 product selector rather than only inside their own teacher replay."
        ),
        "target": "Stage777 fixed target: 500k, AM41, OI confirm risk restore 0.40->0.80, no loss-streak scaling, no recovery sleeve.",
        "year_starts": [start.strftime("%Y-%m") for start in YEAR_STARTS],
        "pool_decisions": pool_decisions,
        "comparison_aggregate": _json_safe(aggregate.to_dict("records")),
        "overall_decision": "stage777_cross_teacher_ai_yearly_complete_not_formal_promotion",
        "outputs": {
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
            "Medium. The pools are generated from prior researched AM41/OI teachers, but this run predeclares exactly two pools and a fixed Stage777 target with no parameter sweep."
        ),
        "continue_value": (
            "Valuable as a yearly promotion gate. Escalate only if a pool improves mature yearly starts without DD50 failure; otherwise continue with intercepted-trade attribution only."
        ),
    }


def _write_report(summary: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    summary_display = summary[
        [
            "pool_name",
            "start_month",
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
            "pool_name",
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
        "# Stage789 两个新 AI 池统一接入 Stage777 年度多起点验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- target：{decision['target']}",
        f"- 年度起点：`{YEAR_STARTS[0].strftime('%Y-%m')}` 到 `{YEAR_STARTS[-1].strftime('%Y-%m')}`，统一终点 `{ANALYSIS_END.date()}`。",
        "- 对比口径：同一 Stage777 target，`AI-off` vs `am41_no_oi` 老师池 vs `am41_oi08` 老师池。",
        "",
        "## Yearly Summary",
        "",
        _md_table(summary_display, max_rows=40),
        "",
        "## AI Pool - Stage777 AI-off",
        "",
        _md_table(detail_display, max_rows=40),
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=20),
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
        f"- pool_decisions：`{json.dumps(decision['pool_decisions'], ensure_ascii=False)}`",
        f"- 过拟合判断：{decision['overfit_reflection']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    eligibility_paths = _eligibility_paths(metadata)
    summary, cost, curves = _run_yearly_targets(eligibility_paths)
    comparison, aggregate = _comparison(summary)
    decision = _decision(summary, comparison, aggregate)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_DETAIL_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(COMPARISON_AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_comparison(comparison)
    _plot_selected_equity(curves)
    _write_report(summary, comparison, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")
    print(f"chart: {COMPARISON_CHART_PATH}")


if __name__ == "__main__":
    main()

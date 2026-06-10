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
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage781_am41_oi08_streak8_monthly as s781


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage784_stage777_no_ai_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage784_stage777_no_ai_yearly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
YEAR_STARTS = tuple(pd.date_range("2018-01-01", "2026-01-01", freq="YS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE784_MAX_WORKERS", "6"))))

CANDIDATE_VARIANT = "stage784_500k_am41_oi08_no_ai_yearly"
CANDIDATE_LABEL = "Stage784 Stage777 AM41 OI0.8 with AI product pool disabled"
PROFILE_NAME = "stage784_stage777_no_ai"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
COMPARISON_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_detail_vs_stage777_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
COMPARISON_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_chart_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None
_WORKER_PROFILE: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"ystart_{start.strftime('%Y')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s757._candidate_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label=CANDIDATE_LABEL,
        note=(
            "Stage777 AM41/OI0.8 logic with only the AI product-pool entry filter disabled. "
            "Product universe, signals, risk multiplier, OI restore, max positions and forced margin shell "
            "are intentionally kept unchanged."
        ),
    )
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
    spec = replace(base, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return {
        "profile": PROFILE_NAME,
        "oi_mode": "oi_restore",
        "am_label": "am40",
        "declared_am_size": 41,
        "strategy_cls": s772.QmtRollPortfolioStrategyExactAm,
        "spec": spec,
        "note": "Research-only Stage777 ablation: AI product pool disabled, all other Stage777 knobs held fixed.",
    }


def _rewrite_outputs(
    row: dict[str, Any],
    costs: list[dict[str, Any]],
    curve: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    row = dict(row)
    row.update(
        {
            "variant": CANDIDATE_VARIANT,
            "label": CANDIDATE_LABEL,
            "profile": PROFILE_NAME,
            "source_name": "stage784_stage777_no_ai_yearly",
            "oi_mode": "oi_restore",
            "am_label": "am40",
            "declared_am_size": 41,
            "ai_product_pool_enabled": 0,
            "note": "Stage777 AM41/OI0.8 yearly-start ablation with AI product-pool filter disabled.",
        }
    )
    for cost in costs:
        cost.update(
            {
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "profile": PROFILE_NAME,
                "source_name": "stage784_stage777_no_ai_yearly",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
                "ai_product_pool_enabled": 0,
            }
        )
    frame = curve.copy()
    frame["variant"] = CANDIDATE_VARIANT
    frame["label"] = CANDIDATE_LABEL
    frame["profile"] = PROFILE_NAME
    frame["source_name"] = "stage784_stage777_no_ai_yearly"
    frame["oi_mode"] = "oi_restore"
    frame["am_label"] = "am40"
    frame["declared_am_size"] = 41
    frame["ai_product_pool_enabled"] = 0
    return row, costs, frame


def _run_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA, _WORKER_PROFILE
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
        _WORKER_PROFILE = _candidate_profile(_WORKER_METADATA)
    metadata = _WORKER_METADATA
    profile = _WORKER_PROFILE
    if profile is None:
        raise RuntimeError("missing worker profile")
    start = pd.Timestamp(task["start"])
    try:
        frame, forced_events = s772._run_engine(
            profile=profile,
            start=start,
            metadata=metadata,
            base_c3_overrides=dict(task["base_c3_overrides"]),
        )
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        row, costs, curve = s781._flat_no_trade_result(task)
        row["window_name"] = _window_name(start)
        row["window_label"] = _window_label(start)
        row["window_group"] = "year_start"
        curve["window_name"] = _window_name(start)
        curve["window_label"] = _window_label(start)
        curve["window_group"] = "year_start"
        return _rewrite_outputs(row, costs, curve)

    spec = profile["spec"]
    row, curve, costs = s772.s748._metric_row(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="year_start",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    curve = s772._curve_common(curve)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
    return _rewrite_outputs(row, costs, curve)


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(YEAR_STARTS[0].to_pydatetime()))
    tasks = [{"start": start.strftime("%Y-%m-%d"), "base_c3_overrides": base_c3_overrides} for start in YEAR_STARTS]

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage784] launching {len(tasks)} yearly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage784] running {idx}/{len(tasks)} {task['start']}", flush=True)
            row, costs, curve = _run_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage784] completed {idx}/{len(tasks)} {task['start']}", flush=True)

    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _profile_aggregate(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, frame in [
        ("all", summary),
        ("mature_252d", summary[summary["mature_252d"].eq(1)]),
    ]:
        returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(frame["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "profile": PROFILE_NAME,
                "bucket": bucket,
                "start_count": int(len(frame)),
                "positive_count": int(frame["positive_return"].sum()) if len(frame) else 0,
                "positive_rate_pct": float(frame["positive_return"].mean() * 100.0) if len(frame) else 0.0,
                "median_return_pct": float(returns.median()) if len(frame) else 0.0,
                "p10_return_pct": float(returns.quantile(0.10)) if len(frame) else 0.0,
                "min_return_pct": float(returns.min()) if len(frame) else 0.0,
                "median_dd_pct": float(dds.median()) if len(frame) else 0.0,
                "worst_dd_pct": float(dds.min()) if len(frame) else 0.0,
                "dd30_fail_count": int((dds < -30.0).sum()) if len(frame) else 0,
                "dd40_fail_count": int(frame["dd40_fail"].sum()) if len(frame) else 0,
                "dd50_fail_count": int(frame["dd50_fail"].sum()) if len(frame) else 0,
                "median_sharpe": float(sharpes.median()) if len(frame) else 0.0,
                "trade_count_median": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").median()) if len(frame) else 0.0,
                "trade_count_sum": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").sum()) if len(frame) else 0.0,
            }
        )

    cost_view = cost[cost["cost_multiplier"].isin([2.0, 3.0])].copy()
    if not cost_view.empty:
        cost_view["dd40_fail"] = (pd.to_numeric(cost_view["max_dd_pct"], errors="coerce") < -40.0).astype(int)
        for multiplier, frame in cost_view.groupby("cost_multiplier", sort=True):
            rows.append(
                {
                    "profile": PROFILE_NAME,
                    "bucket": f"cost_{multiplier}x_all",
                    "start_count": int(summary.shape[0]),
                    "median_return_pct": float(pd.to_numeric(frame["total_return_pct"], errors="coerce").median()),
                    "dd40_fail_count": int(frame["dd40_fail"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _comparison_vs_stage777(summary: pd.DataFrame) -> pd.DataFrame:
    if not s777.SUMMARY_PATH.exists():
        raise FileNotFoundError(s777.SUMMARY_PATH)
    base = pd.read_csv(s777.SUMMARY_PATH, encoding="utf-8-sig")
    base = base[base["start_month"].astype(str).str.endswith("-01")].copy()
    merged = base.merge(summary, on="start_month", suffixes=("_stage777", "_stage784"), how="inner")
    merged["return_delta_pct"] = (
        pd.to_numeric(merged["rebased_total_return_pct_stage784"], errors="coerce")
        - pd.to_numeric(merged["rebased_total_return_pct_stage777"], errors="coerce")
    )
    merged["dd_delta_pp"] = (
        pd.to_numeric(merged["rebased_max_dd_pct_stage784"], errors="coerce")
        - pd.to_numeric(merged["rebased_max_dd_pct_stage777"], errors="coerce")
    )
    merged["sharpe_delta"] = (
        pd.to_numeric(merged["rebased_sharpe_stage784"], errors="coerce")
        - pd.to_numeric(merged["rebased_sharpe_stage777"], errors="coerce")
    )
    merged["trade_count_delta"] = (
        pd.to_numeric(merged["total_trade_count_stage784"], errors="coerce")
        - pd.to_numeric(merged["total_trade_count_stage777"], errors="coerce")
    )
    merged["candidate_return_win"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["candidate_dd_win"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["candidate_both_win"] = (
        merged["candidate_return_win"].eq(1) & merged["candidate_dd_win"].eq(1)
    ).astype(int)
    merged.to_csv(COMPARISON_DETAIL_PATH, index=False, encoding="utf-8-sig")

    rows: list[dict[str, Any]] = []
    for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_stage777"].eq(1)])]:
        rows.append(
            {
                "bucket": bucket,
                "start_count": int(len(frame)),
                "return_win_count": int(frame["candidate_return_win"].sum()) if len(frame) else 0,
                "return_win_rate_pct": float(frame["candidate_return_win"].mean() * 100.0) if len(frame) else 0.0,
                "dd_win_count": int(frame["candidate_dd_win"].sum()) if len(frame) else 0,
                "dd_win_rate_pct": float(frame["candidate_dd_win"].mean() * 100.0) if len(frame) else 0.0,
                "both_win_count": int(frame["candidate_both_win"].sum()) if len(frame) else 0,
                "median_return_delta_pct": float(frame["return_delta_pct"].median()) if len(frame) else 0.0,
                "p10_return_delta_pct": float(frame["return_delta_pct"].quantile(0.10)) if len(frame) else 0.0,
                "min_return_delta_pct": float(frame["return_delta_pct"].min()) if len(frame) else 0.0,
                "median_dd_delta_pp": float(frame["dd_delta_pp"].median()) if len(frame) else 0.0,
                "worst_dd_delta_pp": float(frame["dd_delta_pp"].min()) if len(frame) else 0.0,
                "median_sharpe_delta": float(frame["sharpe_delta"].median()) if len(frame) else 0.0,
                "median_trade_count_delta": float(frame["trade_count_delta"].median()) if len(frame) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _plot_comparison() -> None:
    detail = pd.read_csv(COMPARISON_DETAIL_PATH, encoding="utf-8-sig")
    years = pd.to_datetime(detail["start_month"] + "-01").dt.year.astype(str)
    x = np.arange(len(detail))
    width = 0.36

    ret_777 = pd.to_numeric(detail["rebased_total_return_pct_stage777"], errors="coerce")
    ret_784 = pd.to_numeric(detail["rebased_total_return_pct_stage784"], errors="coerce")
    dd_777 = pd.to_numeric(detail["rebased_max_dd_pct_stage777"], errors="coerce")
    dd_784 = pd.to_numeric(detail["rebased_max_dd_pct_stage784"], errors="coerce")
    tc_777 = pd.to_numeric(detail["total_trade_count_stage777"], errors="coerce")
    tc_784 = pd.to_numeric(detail["total_trade_count_stage784"], errors="coerce")

    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].bar(x - width / 2, ret_777, width=width, label="Stage777 AI on", color="#2563eb")
    axes[0].bar(x + width / 2, ret_784, width=width, label="Stage784 AI off", color="#dc2626")
    axes[0].set_ylabel("Return %")
    axes[0].set_title("Stage777 vs Stage784 yearly-start return")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper right")

    axes[1].bar(x - width / 2, dd_777, width=width, label="Stage777 AI on", color="#2563eb")
    axes[1].bar(x + width / 2, dd_784, width=width, label="Stage784 AI off", color="#dc2626")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=1.0)
    axes[1].set_ylabel("Max DD %")
    axes[1].set_title("Max drawdown")
    axes[1].grid(axis="y", alpha=0.25)

    axes[2].bar(x - width / 2, tc_777, width=width, label="Stage777 AI on", color="#2563eb")
    axes[2].bar(x + width / 2, tc_784, width=width, label="Stage784 AI off", color="#dc2626")
    axes[2].set_ylabel("Trades")
    axes[2].set_title("Total trade count")
    axes[2].grid(axis="y", alpha=0.25)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(years, rotation=0)
    axes[2].set_xlabel("Start year")

    fig.tight_layout()
    fig.savefig(COMPARISON_CHART_PATH, dpi=180)
    plt.close(fig)


def _plot_equity_curves(curves: pd.DataFrame) -> None:
    data = curves.copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab10.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            label=str(start_month),
            color=colors[idx % len(colors)],
            linewidth=1.6,
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage784 AI-off yearly-start equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=9)
    fig.tight_layout()
    fig.savefig(EQUITY_CURVES_PATH, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    mature = profile_agg[profile_agg["bucket"].eq("mature_252d")].iloc[0]
    comp_mature = comparison[comparison["bucket"].eq("mature_252d")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["dd40_fail_count"]) > 0:
        hard_fail.append("mature_dd40_fail_exists")
    if float(comp_mature["return_win_rate_pct"]) < 50.0:
        watch.append("return_win_rate_vs_stage777_below50pct")
    if float(comp_mature["median_return_delta_pct"]) < 0.0:
        watch.append("median_return_delta_vs_stage777_negative")
    if float(comp_mature["median_dd_delta_pp"]) < 0.0:
        watch.append("median_dd_worse_than_stage777")
    decision = "stage777_no_ai_yearly_not_promoted" if hard_fail else "stage777_no_ai_yearly_ablation_only"
    return {
        "stage": "Stage784",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "analysis_start_first": YEAR_STARTS[0].date().isoformat(),
        "analysis_start_last": YEAR_STARTS[-1].date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "yearly_start_count": len(YEAR_STARTS),
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "base_stage": "Stage777 AM41 OI0.8 monthly validation",
            "base_effective_risk_multiplier": 0.40,
            "oi_hit_effective_risk_multiplier": 0.80,
            "ai_product_pool_filter_before": True,
            "ai_product_pool_filter_after": False,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
        },
        "profile_aggregate": profile_agg.to_dict("records"),
        "comparison_vs_stage777": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "profile_aggregate": str(PROFILE_AGG_PATH),
            "comparison": str(COMPARISON_PATH),
            "comparison_detail": str(COMPARISON_DETAIL_PATH),
            "comparison_chart": str(COMPARISON_CHART_PATH),
            "equity_curves": str(EQUITY_CURVES_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "low: this is a one-factor ablation of the existing Stage777 path, not a new fitted parameter. "
            "It should be interpreted as AI dependency evidence only."
        ),
        "continue_value": (
            "yes for diagnosis; promotion requires the AI-off result to improve out-of-sample style start-year "
            "robustness without worsening drawdown."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    detail = pd.read_csv(COMPARISON_DETAIL_PATH, encoding="utf-8-sig")
    display_columns = [
        "start_month",
        "rebased_total_return_pct_stage777",
        "rebased_total_return_pct_stage784",
        "return_delta_pct",
        "rebased_max_dd_pct_stage777",
        "rebased_max_dd_pct_stage784",
        "dd_delta_pp",
        "total_trade_count_stage777",
        "total_trade_count_stage784",
        "trade_count_delta",
    ]
    lines = [
        "# Stage784 Stage777 关闭 AI 选品年度启动消融",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{YEAR_STARTS[0].strftime('%Y-%m')}` 到 `{YEAR_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 口径：Stage777 AM41/OI0.8；只关闭 `enable_ai_product_pool_filter`，其余信号、仓位、强平壳、OI 放大保持不变。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=20),
        "",
        "## Comparison vs Stage777 AI-on",
        "",
        _md_table(comparison, max_rows=20),
        "",
        "## Yearly Detail",
        "",
        _md_table(detail[display_columns], max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail：`{decision['hard_fail_checks']}`",
        f"- watch：`{decision['watch_checks']}`",
        f"- 过拟合判断：{decision['overfit_judgment']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_all()
    profile_agg = _profile_aggregate(summary, cost)
    comparison = _comparison_vs_stage777(summary)
    decision = _build_decision(profile_agg, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_comparison()
    _plot_equity_curves(curves)
    _write_report(profile_agg, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

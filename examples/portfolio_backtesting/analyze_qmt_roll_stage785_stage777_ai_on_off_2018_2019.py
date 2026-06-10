from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage785_stage777_ai_on_off_2018_2019_v1"
OUTPUT_PREFIX = "qmt_roll_stage785_stage777_ai_on_off_2018_2019"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_START = pd.Timestamp("2018-01-01")
ANALYSIS_END = pd.Timestamp("2019-12-31")

AI_ON_VARIANT = "stage785_stage777_ai_on_2018_2019"
AI_OFF_VARIANT = "stage785_stage784_ai_off_2018_2019"
AI_ON_PROFILE = "stage785_stage777_ai_on"
AI_OFF_PROFILE = "stage785_stage784_ai_off"

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


def _window_name() -> str:
    return "period_2018_2019"


def _window_label() -> str:
    return f"{ANALYSIS_START.date()} to {ANALYSIS_END.date()}"


def _stage777_ai_on_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    for profile in s772._profile_specs(metadata):
        if str(profile["profile"]) == "oi_restore_am40":
            base = profile["spec"]
            capital = replace(
                base.capital,
                variant=AI_ON_VARIANT,
                label="Stage777 AI-on AM41 OI0.8 2018-2019",
                note=(
                    "Stage777-equivalent AM41/OI0.8 path for the fixed 2018-2019 slice. "
                    "AI product-pool filter remains enabled through the inherited official Stage78 overrides."
                ),
            )
            spec = replace(base, capital=capital, profile=AI_ON_PROFILE)
            return {
                **profile,
                "profile": AI_ON_PROFILE,
                "spec": spec,
                "source_name": "stage785_stage777_ai_on_2018_2019",
                "ai_product_pool_enabled": 1,
                "note": "Stage777 AI-on fixed 2018-2019 slice.",
            }
    raise RuntimeError("missing oi_restore_am40 profile")


def _stage784_ai_off_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    on_profile = _stage777_ai_on_profile(metadata)
    base = on_profile["spec"]
    capital = replace(
        base.capital,
        variant=AI_OFF_VARIANT,
        label="Stage784 AI-off AM41 OI0.8 2018-2019",
        note=(
            "Stage777-equivalent AM41/OI0.8 path for the fixed 2018-2019 slice, "
            "but AI product-pool entry filtering is disabled."
        ),
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
        **on_profile,
        "profile": AI_OFF_PROFILE,
        "spec": spec,
        "source_name": "stage785_stage784_ai_off_2018_2019",
        "ai_product_pool_enabled": 0,
        "note": "Stage784 AI-off fixed 2018-2019 slice.",
    }


def _run_profile(
    profile: dict[str, Any],
    *,
    metadata: dict[str, Any],
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    s772.ANALYSIS_END = ANALYSIS_END
    frame, forced_events = s772._run_engine(
        profile=profile,
        start=ANALYSIS_START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
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
            "requested_start_month": ANALYSIS_START.strftime("%Y-%m"),
            "start_month": ANALYSIS_START.strftime("%Y-%m"),
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
    curve["requested_start_month"] = ANALYSIS_START.strftime("%Y-%m")
    curve["start_month"] = ANALYSIS_START.strftime("%Y-%m")
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
                "requested_start_month": ANALYSIS_START.strftime("%Y-%m"),
                "start_month": ANALYSIS_START.strftime("%Y-%m"),
                "fixed_period": "2018-2019",
            }
        )
    return row, costs, curve


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(ANALYSIS_START.to_pydatetime()))
    profiles = [_stage777_ai_on_profile(metadata), _stage784_ai_off_profile(metadata)]
    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for profile in profiles:
        print(f"[stage785] running {profile['profile']} {ANALYSIS_START.date()}->{ANALYSIS_END.date()}", flush=True)
        row, costs, curve = _run_profile(profile, metadata=metadata, base_c3_overrides=base_c3_overrides)
        rows.append(row)
        cost_rows.extend(costs)
        curves.append(curve)
    summary = pd.DataFrame(rows).sort_values("ai_product_pool_enabled", ascending=False).reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["ai_product_pool_enabled", "cost_multiplier"], ascending=[False, True]).reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["ai_product_pool_enabled", "date"], ascending=[False, True]).reset_index(drop=True)
    return summary, cost, curves_all


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    on = summary[summary["ai_product_pool_enabled"].eq(1)].iloc[0]
    off = summary[summary["ai_product_pool_enabled"].eq(0)].iloc[0]
    keys = [
        ("end_equity", "end_equity_delta"),
        ("rebased_total_return_pct", "return_delta_pct"),
        ("rebased_max_dd_pct", "dd_delta_pp"),
        ("rebased_sharpe", "sharpe_delta"),
        ("total_slippage", "slippage_delta"),
        ("total_trade_count", "trade_count_delta"),
        ("nonzero_daily_win_rate_pct", "win_rate_delta_pp"),
        ("max_broker10_margin_to_equity_pct", "max_margin_delta_pp"),
        ("forced_margin_deleverage_count", "forced_count_delta"),
    ]
    row: dict[str, Any] = {
        "period": "2018-01-01_to_2019-12-31",
        "ai_on_variant": on["variant"],
        "ai_off_variant": off["variant"],
    }
    for key, out_key in keys:
        row[f"ai_on_{key}"] = float(pd.to_numeric(pd.Series([on.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
        row[f"ai_off_{key}"] = float(pd.to_numeric(pd.Series([off.get(key, 0.0)]), errors="coerce").fillna(0.0).iloc[0])
        row[out_key] = row[f"ai_off_{key}"] - row[f"ai_on_{key}"]
    row["ai_off_return_win"] = int(row["return_delta_pct"] > 0.0)
    row["ai_off_dd_win"] = int(row["dd_delta_pp"] > 0.0)
    return pd.DataFrame([row])


def _plot(curves: pd.DataFrame) -> None:
    data = curves.copy()
    labels = {
        AI_ON_VARIANT: "Stage777 AI on",
        AI_OFF_VARIANT: "Stage784 AI off",
    }
    colors = {
        AI_ON_VARIANT: "#2563eb",
        AI_OFF_VARIANT: "#dc2626",
    }
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for variant, group in data.groupby("variant", sort=False):
        group = group.sort_values("date")
        dates = pd.to_datetime(group["date"])
        equity = pd.to_numeric(group["account_equity"], errors="coerce")
        peak = equity.cummax()
        dd = (equity / peak.replace(0.0, np.nan) - 1.0).fillna(0.0) * 100.0
        axes[0].plot(dates, equity / 1_000_000, label=labels.get(variant, variant), color=colors.get(variant), linewidth=1.8)
        axes[1].plot(dates, dd, label=labels.get(variant, variant), color=colors.get(variant), linewidth=1.6)
    axes[0].axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    axes[0].set_title("Stage777 AI-on vs Stage784 AI-off: 2018-2019 fixed period")
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


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    row = comparison.iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(row["ai_off_return_win"]) == 0:
        hard_fail.append("ai_off_return_not_better")
    if int(row["ai_off_dd_win"]) == 0:
        hard_fail.append("ai_off_drawdown_not_better")
    if float(row["ai_off_rebased_max_dd_pct"]) < -40.0:
        hard_fail.append("ai_off_dd40_fail")
    if float(row["trade_count_delta"]) > 0:
        watch.append("ai_off_adds_trades")
    return {
        "stage": "Stage785",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "stage777_ai_off_2018_2019_not_promoted" if hard_fail else "stage777_ai_off_2018_2019_candidate_watch",
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "versions_compared": ["Stage777 AI-on AM41/OI0.8", "Stage784 AI-off AM41/OI0.8"],
            "base_effective_risk_multiplier": 0.40,
            "oi_hit_effective_risk_multiplier": 0.80,
            "fixed_period": "2018-2019",
        },
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "low as an ablation slice: no new parameter is fitted, but the 2018-2019 slice must not be used "
            "to tune the AI filter because it is only one regime block."
        ),
        "continue_value": (
            "yes for diagnosis of the early data-extension window; no for promotion if AI-off only adds trades "
            "without improving return and drawdown."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(summary: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    columns = [
        "variant",
        "label",
        "end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "forced_margin_deleverage_count",
    ]
    lines = [
        "# Stage785 Stage777 AI-on vs AI-off 2018-2019 固定窗口",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 固定窗口：`{ANALYSIS_START.date()}` 到 `{ANALYSIS_END.date()}`。",
        "- 口径：两个版本都保留 Stage777 AM41/OI0.8；第二个版本只关闭 AI 产品池过滤。",
        "",
        "## Summary",
        "",
        _md_table(summary[columns], max_rows=10),
        "",
        "## Comparison",
        "",
        _md_table(comparison, max_rows=10),
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
    comparison = _comparison(summary)
    decision = _decision(summary, comparison)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(summary, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

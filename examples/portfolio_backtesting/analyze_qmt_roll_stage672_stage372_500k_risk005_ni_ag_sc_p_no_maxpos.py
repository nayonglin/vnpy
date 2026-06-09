from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab as s667
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos_v1"
OUTPUT_PREFIX = "qmt_roll_stage672_stage372_500k_risk005_ni_ag_sc_p_no_maxpos"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CAPITAL = 500_000.0
RISK_MULTIPLIER = 0.05
EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE", "sc.INE", "p.DCE")
PLUS_COMBO_STRATEGY = "stage672_stage372_500k_risk005_plus_ni_ag_sc_p_no_maxpos_entry_filter"
SOURCE_LABEL = "stage672_500k_risk005_plus_ni_ag_sc_p_no_maxpos"
SCORE_TYPE = "stage672_fixed_add_four_ni_ag_sc_p_no_maxpos"
STAGE_NAME = "Stage384"
SCRIPT_STAGE = "Stage672"
RISK_LABEL = "risk005"
REPORT_TITLE = "# Stage672 50万 risk0.05 加 ni/ag/sc/p 后放宽持仓限制审计"
CHART_TITLE = "Stage672 500k risk005 + ni/ag/sc/p maxpos4 vs maxpos23"
REJECT_DECISION = "stage372_500k_risk005_plus_four_no_maxpos_rejected"
WATCH_DECISION = "stage372_500k_risk005_plus_four_no_maxpos_watch_not_auto_promote"
PASS_DECISION = "stage372_500k_risk005_plus_four_no_maxpos_passes_first_gate"

BASE_VARIANT = "stage372_500k_risk005_plus_ni_ag_sc_p_maxpos4"
CANDIDATE_VARIANT = "stage372_500k_risk005_plus_ni_ag_sc_p_maxpos23"
BASE_MAXPOS = 4

GENERATED_DIR = OUTPUT_DIR / "stage672_generated_inputs"
UNIVERSE_PLUS_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_ni_ag_sc_p_universe_{MODEL_TAG}.csv"
HIST_ELIGIBILITY_PLUS_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"
LATEST_ELIGIBILITY_PLUS_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_plus_ni_ag_sc_p_eligibility_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_activity_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s667._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s667._md_table(frame, max_rows=max_rows)


def _product_code(product_vt_symbol: str) -> str:
    return product_vt_symbol.split(".", 1)[0]


def _configure_shared_runner() -> None:
    s667.MODEL_TAG = MODEL_TAG
    s667.OUTPUT_PREFIX = OUTPUT_PREFIX
    s667.EXTRA_PRODUCTS = EXTRA_PRODUCTS
    s667.PLUS_COMBO_STRATEGY = PLUS_COMBO_STRATEGY
    s667.SOURCE_LABEL = SOURCE_LABEL
    s667.SCORE_TYPE = SCORE_TYPE
    s667.STAGE_NAME = STAGE_NAME
    s667.SCRIPT_STAGE = SCRIPT_STAGE
    s667.REPORT_TITLE = REPORT_TITLE
    s667.VARIANT_PLUS_COMBO = BASE_VARIANT
    s667.GENERATED_DIR = GENERATED_DIR
    s667.UNIVERSE_PLUS_COMBO_PATH = UNIVERSE_PLUS_PATH
    s667.HIST_ELIGIBILITY_PLUS_COMBO_PATH = HIST_ELIGIBILITY_PLUS_PATH
    s667.LATEST_ELIGIBILITY_PLUS_COMBO_PATH = LATEST_ELIGIBILITY_PLUS_PATH


def _with_maxpos(spec: Any, *, variant: str, label: str, maxpos: int) -> Any:
    capital = replace(
        spec.capital,
        variant=variant,
        label=label,
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER,
        max_concurrent_positions=maxpos,
        note=(
            f"{SCRIPT_STAGE}: keep 500k/{RISK_LABEL} plus {', '.join(EXTRA_PRODUCTS)}, "
            f"set max_concurrent_positions={maxpos}."
        ),
    )
    overrides = {**spec.overrides, "max_concurrent_positions": maxpos}
    return replace(spec, capital=capital, overrides=overrides, profile=variant)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["variant"].eq(BASE_VARIANT)].set_index("window_name")
    candidate = summary[summary["variant"].eq(CANDIDATE_VARIANT)].set_index("window_name")
    base_cost = cost[(cost["variant"].eq(BASE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    candidate_cost = cost[
        (cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))
    ].set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in candidate.index:
        if name not in base.index:
            continue
        b = base.loc[name]
        c = candidate.loc[name]
        row = {
            "window_name": name,
            "window_label": c["window_label"],
            "window_group": c["window_group"],
            "base_return_pct": float(b["rebased_total_return_pct"]),
            "candidate_return_pct": float(c["rebased_total_return_pct"]),
            "delta_return_pct": float(c["rebased_total_return_pct"] - b["rebased_total_return_pct"]),
            "base_max_dd_pct": float(b["rebased_max_dd_pct"]),
            "candidate_max_dd_pct": float(c["rebased_max_dd_pct"]),
            "delta_max_dd_pct": float(c["rebased_max_dd_pct"] - b["rebased_max_dd_pct"]),
            "base_sharpe": float(b["rebased_sharpe"]),
            "candidate_sharpe": float(c["rebased_sharpe"]),
            "delta_sharpe": float(c["rebased_sharpe"] - b["rebased_sharpe"]),
            "base_trades": float(b["total_trade_count"]),
            "candidate_trades": float(c["total_trade_count"]),
            "delta_trades": float(c["total_trade_count"] - b["total_trade_count"]),
            "base_slippage": float(b["total_slippage"]),
            "candidate_slippage": float(c["total_slippage"]),
            "delta_slippage": float(c["total_slippage"] - b["total_slippage"]),
            "base_margin_peak_pct": float(b["max_broker10_margin_to_rebased_equity_pct"]),
            "candidate_margin_peak_pct": float(c["max_broker10_margin_to_rebased_equity_pct"]),
            "delta_margin_peak_pct": float(
                c["max_broker10_margin_to_rebased_equity_pct"]
                - b["max_broker10_margin_to_rebased_equity_pct"]
            ),
        }
        if name in base_cost.index and name in candidate_cost.index:
            row["base_2x_max_dd_pct"] = float(base_cost.loc[name, "max_dd_pct"])
            row["candidate_2x_max_dd_pct"] = float(candidate_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(candidate_cost.loc[name, "max_dd_pct"] - base_cost.loc[name, "max_dd_pct"])
        rows.append(row)
    return pd.DataFrame(rows)


def _margin_usage(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full = curves[curves["window_name"].eq("full_2020_20260430")]
    for variant, frame in full.groupby("variant", sort=True):
        margin = pd.to_numeric(frame["broker10_margin_to_rebased_equity_pct"], errors="coerce").fillna(0.0)
        active = margin.gt(1e-9)
        rows.append(
            {
                "variant": variant,
                "active_days": int(active.sum()),
                "active_rate_pct": float(active.mean() * 100.0),
                "avg_margin_all_days_pct": float(margin.mean()),
                "avg_margin_active_days_pct": float(margin[active].mean()) if int(active.sum()) else 0.0,
                "p95_margin_pct": float(margin.quantile(0.95)),
                "max_margin_pct": float(margin.max()),
                "days_gt_30pct": int(margin.gt(30.0).sum()),
                "days_gt_50pct": int(margin.gt(50.0).sum()),
                "days_gt_70pct": int(margin.gt(70.0).sum()),
                "days_gt_90pct": int(margin.gt(90.0).sum()),
                "days_gt_100pct": int(margin.gt(100.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _checks(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    candidate_full = summary[
        (summary["variant"].eq(CANDIDATE_VARIANT)) & (summary["window_name"].eq("full_2020_20260430"))
    ]
    candidate_cost2 = cost[
        (cost["variant"].eq(CANDIDATE_VARIANT))
        & (cost["window_name"].eq("full_2020_20260430"))
        & (cost["cost_multiplier"].eq(2.0))
    ]

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    if not full_cmp.empty:
        row = full_cmp.iloc[0]
        add(
            "candidate_return_improves",
            "pass" if float(row["delta_return_pct"]) > 0 else "fail",
            float(row["delta_return_pct"]),
            "> 0",
            "放宽持仓限制至少应提升四品种低风险口径全周期收益。",
        )
        add(
            "candidate_sharpe_not_worse",
            "pass" if float(row["delta_sharpe"]) >= -0.03 else "fail",
            float(row["delta_sharpe"]),
            ">= -0.03",
            "风险收益比不能明显恶化。",
        )
        add(
            "candidate_dd_not_materially_worse",
            "pass" if float(row["delta_max_dd_pct"]) >= -2.0 else "fail",
            float(row["delta_max_dd_pct"]),
            ">= -2pp vs A",
            "正常成本最大回撤不能明显恶化。",
        )
        add(
            "candidate_2x_dd_not_materially_worse",
            "pass" if float(row.get("delta_2x_max_dd_pct", -999.0)) >= -2.0 else "fail",
            float(row.get("delta_2x_max_dd_pct", -999.0)),
            ">= -2pp vs A",
            "2x成本回撤不能明显恶化。",
        )
        add(
            "candidate_margin_peak_not_much_worse",
            "pass" if float(row["delta_margin_peak_pct"]) <= 5.0 else "fail",
            float(row["delta_margin_peak_pct"]),
            "<= +5pp",
            "低风险口径下放宽持仓不应明显提高保证金峰值。",
        )
    if not candidate_full.empty:
        row = candidate_full.iloc[0]
        add(
            "candidate_dd40",
            "pass" if float(row["rebased_max_dd_pct"]) >= -40.0 else "fail",
            float(row["rebased_max_dd_pct"]),
            ">= -40",
            "候选全周期正常成本最大回撤。",
        )
        add(
            "candidate_margin100",
            "pass" if int(row["days_over_100pct"]) == 0 else "fail",
            float(row["days_over_100pct"]),
            "0 days",
            "候选 broker10 保证金不穿100%。",
        )
    if not candidate_cost2.empty:
        row = candidate_cost2.iloc[0]
        add(
            "candidate_2x_cost_dd40",
            "pass" if float(row["max_dd_pct"]) >= -40.0 else "fail",
            float(row["max_dd_pct"]),
            ">= -40",
            "候选全周期2x成本压力回撤。",
        )
    candidate_rolling = rolling[rolling["variant"].eq(CANDIDATE_VARIANT)]
    if not candidate_rolling.empty:
        add(
            "rolling_p05_return_min",
            "watch" if float(candidate_rolling["p05_return_pct"].min()) < 0.0 else "pass",
            float(candidate_rolling["p05_return_pct"].min()),
            ">= 0 preferred",
            "任意启动短周期左尾。",
        )
    return pd.DataFrame(rows)


def _activity_with_variant(variant: str, positions: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    activity = s667._extra_activity(positions, usage)
    if activity.empty:
        return activity
    activity.insert(0, "variant", variant)
    return activity


def _plot(curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_delta, ax_margin = axes.flatten()
    full = curves[curves["window_name"].eq("full_2020_20260430")].copy()
    for variant, group in full.groupby("variant", sort=False):
        group = group.sort_values("date")
        dates = pd.to_datetime(group["date"])
        ax_nav.plot(dates, group["rebased_nav"], linewidth=1.1, label=variant)
        ax_dd.plot(dates, group["drawdown_pct"], linewidth=1.0, label=variant)
        ax_margin.plot(dates, group["broker10_margin_to_rebased_equity_pct"], linewidth=1.0, label=variant)
    view = comparison[comparison["window_group"].isin(["historical_full", "start_year", "market_phase", "latest_ytd"])]
    ax_delta.bar(view["window_name"], view["delta_return_pct"].astype(float), color="#2ca02c")
    ax_delta.axhline(0.0, color="#333333", linewidth=0.8)
    ax_delta.tick_params(axis="x", rotation=35)
    ax_nav.set_title("Full NAV")
    ax_dd.set_title("Full drawdown")
    ax_delta.set_title("Candidate - Base return")
    ax_margin.set_title("Broker10 margin / equity")
    for ax in (ax_nav, ax_dd, ax_delta, ax_margin):
        ax.grid(alpha=0.25)
    for ax in (ax_nav, ax_dd, ax_margin):
        ax.legend(fontsize=8)
    ax_dd.axhline(-40.0, color="#111111", linestyle="--", linewidth=0.8)
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    fig.suptitle(CHART_TITLE, fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _decision(
    *,
    prepared: dict[str, Any],
    candidate_limit: int,
    checks: pd.DataFrame,
) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_name = REJECT_DECISION
    if not hard_fail:
        decision_name = WATCH_DECISION if watch else PASS_DECISION
    return {
        "stage": STAGE_NAME,
        "script_stage": SCRIPT_STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "candidate_change": {
            "capital": CAPITAL,
            "risk_multiplier": RISK_MULTIPLIER,
            "extra_products": list(EXTRA_PRODUCTS),
            "max_concurrent_positions_before": BASE_MAXPOS,
            "max_concurrent_positions_after": candidate_limit,
            "official_config_changed": False,
        },
        "decision": decision_name,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks.to_dict("records"),
        "inputs": {
            "base_symbols": prepared["base_symbols"],
            "plus_symbols": prepared["plus_symbols"],
            "historical_eligibility_source": prepared["historical_eligibility_source"],
            "latest_eligibility_source": prepared["latest_eligibility_source"],
            "plus_universe": str(UNIVERSE_PLUS_PATH),
            "plus_historical_eligibility": str(HIST_ELIGIBILITY_PLUS_PATH),
            "plus_latest_eligibility": str(LATEST_ELIGIBILITY_PLUS_PATH),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "rolling": str(ROLLING_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "margin": str(MARGIN_PATH),
            "curves": str(CURVES_PATH),
            "activity": str(ACTIVITY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    rolling: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    margin: pd.DataFrame,
    activity: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "variant",
        "window_name",
        "analysis_start",
        "analysis_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "deployable_pass",
    ]
    lines = [
        REPORT_TITLE,
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- A：`{BASE_VARIANT}`，50万、`risk_multiplier={RISK_MULTIPLIER}`、固定加入 `{', '.join(EXTRA_PRODUCTS)}`、`max_concurrent_positions={BASE_MAXPOS}`。",
        f"- C：`{CANDIDATE_VARIANT}`，只把 `max_concurrent_positions` 放宽到 `{decision['candidate_change']['max_concurrent_positions_after']}`。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 检查",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期结果",
        "",
        _md_table(summary[key_cols], max_rows=140),
        "",
        "## C vs A",
        "",
        _md_table(comparison, max_rows=100),
        "",
        "## 资金占用",
        "",
        _md_table(margin, max_rows=20),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=180),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling, max_rows=80),
        "",
        "## 年度结果",
        "",
        _md_table(annual, max_rows=40),
        "",
        "## 月度结果",
        "",
        _md_table(monthly, max_rows=160),
        "",
        "## 新增品种活跃度",
        "",
        _md_table(activity, max_rows=40),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _configure_shared_runner()
    prepared = s667._prepare_inputs()
    candidate_limit = len(prepared["plus_symbols"])
    base_plus = s667._plus_combo_500k_spec(prepared["plus_metadata"])
    base_spec = _with_maxpos(
        base_plus,
        variant=BASE_VARIANT,
        label=f"50w {RISK_LABEL} plus-ni-ag-sc-p maxpos4",
        maxpos=BASE_MAXPOS,
    )
    candidate_spec = _with_maxpos(
        base_plus,
        variant=CANDIDATE_VARIANT,
        label=f"50w {RISK_LABEL} plus-ni-ag-sc-p maxpos{candidate_limit}",
        maxpos=candidate_limit,
    )

    all_summary_rows: list[dict[str, Any]] = []
    all_curve_frames: list[pd.DataFrame] = []
    all_cost_rows: list[dict[str, Any]] = []
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    activity_frames: list[pd.DataFrame] = []

    for spec in (base_spec, candidate_spec):
        summary, curves, cost, positions, usage, annual, monthly = s667.s666._run_variant_suite(
            spec=spec,
            metadata=prepared["plus_metadata"],
            latest_ai_path=LATEST_ELIGIBILITY_PLUS_PATH,
        )
        all_summary_rows.extend(summary)
        all_curve_frames.extend(curves)
        all_cost_rows.extend(cost)
        if not annual.empty:
            annual_frames.append(annual)
        if not monthly.empty:
            monthly_frames.append(monthly)
        activity = _activity_with_variant(spec.capital.variant, positions, usage)
        if not activity.empty:
            activity_frames.append(activity)

    summary = pd.DataFrame(all_summary_rows)
    curves = pd.concat(all_curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(all_cost_rows)
    comparison = _comparison(summary, cost)
    rolling = s667.s666._rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    annual = pd.concat(annual_frames, ignore_index=True, sort=False) if annual_frames else pd.DataFrame()
    monthly = pd.concat(monthly_frames, ignore_index=True, sort=False) if monthly_frames else pd.DataFrame()
    margin = _margin_usage(curves)
    activity = pd.concat(activity_frames, ignore_index=True, sort=False) if activity_frames else pd.DataFrame()
    checks = _checks(summary, cost, comparison, rolling)
    decision = _decision(prepared=prepared, candidate_limit=candidate_limit, checks=checks)

    _plot(curves, comparison)
    _write_report(summary, cost, comparison, rolling, annual, monthly, margin, activity, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    margin.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    activity.to_csv(ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

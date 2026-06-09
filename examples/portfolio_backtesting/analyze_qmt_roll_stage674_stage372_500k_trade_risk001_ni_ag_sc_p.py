from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab as s667
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage674_stage372_500k_trade_risk001_ni_ag_sc_p_v1"
OUTPUT_PREFIX = "qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p"
LINE_ID = "futures_trend_drawdown30_preserve_return"
STAGE_NAME = "Stage386"
SCRIPT_STAGE = "Stage674"
REPORT_TITLE = "# Stage674 50万 单笔交易风险资金1% + ni/ag/sc/p 审计"
RUNNER_REPORT_TITLE = "# Stage674 50万 单笔风险1% 加 ni/ag/sc/p 审计"
RISK_COMPARE_NAME = "risk001_maxpos4_vs_risk004_maxpos4"
MAXPOS_COMPARE_NAME = "risk001_maxpos23_vs_risk001_maxpos4"
DECISION_WATCH_NAME = "stage372_500k_trade_risk001_plus_four_watch_not_auto_promote"
DECISION_REJECT_NAME = "stage372_500k_trade_risk001_plus_four_rejected"

CAPITAL = 500_000.0
BASE_TRADE_RISK_RATIO = 0.04
TARGET_TRADE_RISK_RATIO = 0.01
EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE", "sc.INE", "p.DCE")
PLUS_COMBO_STRATEGY = "stage674_stage372_500k_trade_risk001_plus_ni_ag_sc_p_entry_filter"
SOURCE_LABEL = "stage674_500k_trade_risk001_plus_ni_ag_sc_p"
SCORE_TYPE = "stage674_fixed_add_four_ni_ag_sc_p_trade_risk001"

BASE_VARIANT = "stage372_500k_trade_risk004_plus_ni_ag_sc_p_maxpos4"
TARGET_VARIANT = "stage372_500k_trade_risk001_plus_ni_ag_sc_p_maxpos4"
TARGET_NO_MAXPOS_VARIANT = "stage372_500k_trade_risk001_plus_ni_ag_sc_p_maxpos23"
BASE_MAXPOS = 4

GENERATED_DIR = OUTPUT_DIR / "stage674_generated_inputs"
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
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


RISK_RATIO_FIELDS = (
    "risk_ratio_of_total_assets",
    "risk_ratio_breakout",
    "risk_ratio_ma_cross_breakout",
    "risk_ratio_open_interest_surge",
    "risk_ratio_open_interest_decline",
    "risk_ratio_volume_open_interest_surge",
)


def _json_safe(value: Any) -> Any:
    return s667._json_safe(value)


def _extra_products_label() -> str:
    products = [symbol.split(".", 1)[0] for symbol in EXTRA_PRODUCTS]
    return "plus-" + "-".join(products)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s667._md_table(frame, max_rows=max_rows)


def _configure_shared_runner() -> None:
    s667.MODEL_TAG = MODEL_TAG
    s667.OUTPUT_PREFIX = OUTPUT_PREFIX
    s667.EXTRA_PRODUCTS = EXTRA_PRODUCTS
    s667.PLUS_COMBO_STRATEGY = PLUS_COMBO_STRATEGY
    s667.SOURCE_LABEL = SOURCE_LABEL
    s667.SCORE_TYPE = SCORE_TYPE
    s667.STAGE_NAME = STAGE_NAME
    s667.SCRIPT_STAGE = SCRIPT_STAGE
    s667.REPORT_TITLE = RUNNER_REPORT_TITLE
    s667.VARIANT_PLUS_COMBO = TARGET_VARIANT
    s667.GENERATED_DIR = GENERATED_DIR
    s667.UNIVERSE_PLUS_COMBO_PATH = UNIVERSE_PLUS_PATH
    s667.HIST_ELIGIBILITY_PLUS_COMBO_PATH = HIST_ELIGIBILITY_PLUS_PATH
    s667.LATEST_ELIGIBILITY_PLUS_COMBO_PATH = LATEST_ELIGIBILITY_PLUS_PATH


def _risk_ratio_overrides(risk_ratio: float) -> dict[str, float]:
    return {field: float(risk_ratio) for field in RISK_RATIO_FIELDS}


def _risk_multiplier_for_record(risk_ratio: float) -> float:
    base = float(s667.s666.s653.s517.BASE_RISK_RATIO)
    return float(risk_ratio) / base if base else 1.0


def _spec_with_trade_risk(base_spec: Any, *, variant: str, label: str, trade_risk_ratio: float, maxpos: int) -> Any:
    capital = replace(
        base_spec.capital,
        variant=variant,
        label=label,
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=_risk_multiplier_for_record(trade_risk_ratio),
        max_concurrent_positions=maxpos,
        note=(
            f"{SCRIPT_STAGE}: override all strategy risk_ratio_* fields to "
            f"{trade_risk_ratio:.4f}; max_concurrent_positions={maxpos}."
        ),
    )
    overrides = {
        **base_spec.overrides,
        **_risk_ratio_overrides(trade_risk_ratio),
        "max_concurrent_positions": int(maxpos),
    }
    return replace(base_spec, capital=capital, overrides=overrides, profile=variant)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASE_VARIANT)].set_index("window_name")
    target = summary[summary["variant"].eq(TARGET_VARIANT)].set_index("window_name")
    no_max = summary[summary["variant"].eq(TARGET_NO_MAXPOS_VARIANT)].set_index("window_name")
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].copy()
    cost2_by_variant = {variant: frame.set_index("window_name") for variant, frame in cost2.groupby("variant")}
    rows: list[dict[str, Any]] = []
    for compare_name, candidate in (
        (RISK_COMPARE_NAME, target),
        (MAXPOS_COMPARE_NAME, no_max),
    ):
        ref = baseline if compare_name.endswith("risk004_maxpos4") else target
        ref_variant = BASE_VARIANT if compare_name.endswith("risk004_maxpos4") else TARGET_VARIANT
        cand_variant = TARGET_VARIANT if compare_name.endswith("risk004_maxpos4") else TARGET_NO_MAXPOS_VARIANT
        for name in candidate.index:
            if name not in ref.index:
                continue
            a = ref.loc[name]
            c = candidate.loc[name]
            row = {
                "compare_name": compare_name,
                "window_name": name,
                "window_label": c["window_label"],
                "window_group": c["window_group"],
                "reference_variant": ref_variant,
                "candidate_variant": cand_variant,
                "reference_return_pct": float(a["rebased_total_return_pct"]),
                "candidate_return_pct": float(c["rebased_total_return_pct"]),
                "delta_return_pct": float(c["rebased_total_return_pct"] - a["rebased_total_return_pct"]),
                "reference_max_dd_pct": float(a["rebased_max_dd_pct"]),
                "candidate_max_dd_pct": float(c["rebased_max_dd_pct"]),
                "delta_max_dd_pct": float(c["rebased_max_dd_pct"] - a["rebased_max_dd_pct"]),
                "reference_sharpe": float(a["rebased_sharpe"]),
                "candidate_sharpe": float(c["rebased_sharpe"]),
                "delta_sharpe": float(c["rebased_sharpe"] - a["rebased_sharpe"]),
                "reference_trades": float(a["total_trade_count"]),
                "candidate_trades": float(c["total_trade_count"]),
                "delta_trades": float(c["total_trade_count"] - a["total_trade_count"]),
                "reference_slippage": float(a["total_slippage"]),
                "candidate_slippage": float(c["total_slippage"]),
                "delta_slippage": float(c["total_slippage"] - a["total_slippage"]),
                "reference_margin_peak_pct": float(a["max_broker10_margin_to_rebased_equity_pct"]),
                "candidate_margin_peak_pct": float(c["max_broker10_margin_to_rebased_equity_pct"]),
                "delta_margin_peak_pct": float(
                    c["max_broker10_margin_to_rebased_equity_pct"]
                    - a["max_broker10_margin_to_rebased_equity_pct"]
                ),
            }
            ref_cost = cost2_by_variant.get(ref_variant, pd.DataFrame())
            cand_cost = cost2_by_variant.get(cand_variant, pd.DataFrame())
            if not ref_cost.empty and not cand_cost.empty and name in ref_cost.index and name in cand_cost.index:
                row["reference_2x_max_dd_pct"] = float(ref_cost.loc[name, "max_dd_pct"])
                row["candidate_2x_max_dd_pct"] = float(cand_cost.loc[name, "max_dd_pct"])
                row["delta_2x_max_dd_pct"] = float(cand_cost.loc[name, "max_dd_pct"] - ref_cost.loc[name, "max_dd_pct"])
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


def _checks(summary: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full_risk = comparison[
        comparison["compare_name"].eq(RISK_COMPARE_NAME)
        & comparison["window_name"].eq("full_2020_20260430")
    ]
    full_maxpos = comparison[
        comparison["compare_name"].eq(MAXPOS_COMPARE_NAME)
        & comparison["window_name"].eq("full_2020_20260430")
    ]
    target_full = summary[
        summary["variant"].eq(TARGET_VARIANT)
        & summary["window_name"].eq("full_2020_20260430")
    ]

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    if not target_full.empty:
        row = target_full.iloc[0]
        add("target_dd30", "pass" if float(row["rebased_max_dd_pct"]) >= -30.0 else "fail", float(row["rebased_max_dd_pct"]), ">= -30", "单笔风险候选最大回撤。")
        add("target_margin100", "pass" if int(row["days_over_100pct"]) == 0 else "fail", float(row["days_over_100pct"]), "0 days", "单笔风险候选保证金不穿100%。")
        add("target_return_positive", "pass" if float(row["rebased_total_return_pct"]) > 0 else "fail", float(row["rebased_total_return_pct"]), "> 0", "单笔风险候选长期收益应为正。")
    if not full_risk.empty:
        row = full_risk.iloc[0]
        add("target_return_retention", "pass" if float(row["candidate_return_pct"]) >= 50.0 else "fail", float(row["candidate_return_pct"]), ">= 50%", "降低单笔风险后收益不能完全失效。")
        add("target_dd_improves", "pass" if float(row["delta_max_dd_pct"]) >= 0.0 else "watch", float(row["delta_max_dd_pct"]), ">= 0pp", "降低单笔风险应改善或至少不恶化回撤。")
    if not full_maxpos.empty:
        row = full_maxpos.iloc[0]
        add("no_maxpos_return_improves", "pass" if float(row["delta_return_pct"]) > 0.0 else "fail", float(row["delta_return_pct"]), "> 0", "同为目标单笔风险时，放宽并发至少应提升收益。")
    return pd.DataFrame(rows)


def _activity_with_variant(variant: str, positions: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    activity = s667._extra_activity(positions, usage)
    if activity.empty:
        return activity
    activity.insert(0, "variant", variant)
    return activity


def _decision(checks: pd.DataFrame, prepared: dict[str, Any]) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_name = DECISION_WATCH_NAME
    if "target_dd30" in hard_fail or "target_return_positive" in hard_fail:
        decision_name = DECISION_REJECT_NAME
    return {
        "stage": STAGE_NAME,
        "script_stage": SCRIPT_STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "baseline": BASE_VARIANT,
        "candidate": TARGET_VARIANT,
        "candidate_no_maxpos": TARGET_NO_MAXPOS_VARIANT,
        "candidate_change": {
            "capital": CAPITAL,
            "extra_products": list(EXTRA_PRODUCTS),
            "base_trade_risk_ratio": BASE_TRADE_RISK_RATIO,
            "target_trade_risk_ratio": TARGET_TRADE_RISK_RATIO,
            "risk_ratio_fields_overridden": list(RISK_RATIO_FIELDS),
            "max_concurrent_positions_base": BASE_MAXPOS,
            "max_concurrent_positions_no_maxpos": len(prepared["plus_symbols"]),
            "official_config_changed": False,
        },
        "decision": decision_name,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks.to_dict("records"),
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
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "deployable_pass",
    ]
    lines = [
        REPORT_TITLE,
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- A：`{BASE_VARIANT}`，全部 `risk_ratio_*={BASE_TRADE_RISK_RATIO}`，`maxpos=4`。",
        f"- C：`{TARGET_VARIANT}`，全部 `risk_ratio_*={TARGET_TRADE_RISK_RATIO}`，`maxpos=4`。",
        f"- C2：`{TARGET_NO_MAXPOS_VARIANT}`，全部 `risk_ratio_*={TARGET_TRADE_RISK_RATIO}`，`maxpos={decision['candidate_change']['max_concurrent_positions_no_maxpos']}`。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 检查",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期结果",
        "",
        _md_table(summary[key_cols], max_rows=160),
        "",
        "## 对比",
        "",
        _md_table(comparison, max_rows=120),
        "",
        "## 资金占用",
        "",
        _md_table(margin, max_rows=30),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=240),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling, max_rows=90),
        "",
        "## 年度结果",
        "",
        _md_table(annual, max_rows=60),
        "",
        "## 新增品种活跃度",
        "",
        _md_table(activity, max_rows=60),
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
    no_maxpos = len(prepared["plus_symbols"])
    base_plus = s667._plus_combo_500k_spec(prepared["plus_metadata"])
    target_risk_label = f"{TARGET_TRADE_RISK_RATIO * 100:.0f}pct"
    product_label = _extra_products_label()
    specs = [
        _spec_with_trade_risk(
            base_plus,
            variant=BASE_VARIANT,
            label=f"50w trade-risk4pct {product_label} maxpos4",
            trade_risk_ratio=BASE_TRADE_RISK_RATIO,
            maxpos=BASE_MAXPOS,
        ),
        _spec_with_trade_risk(
            base_plus,
            variant=TARGET_VARIANT,
            label=f"50w trade-risk{target_risk_label} {product_label} maxpos4",
            trade_risk_ratio=TARGET_TRADE_RISK_RATIO,
            maxpos=BASE_MAXPOS,
        ),
        _spec_with_trade_risk(
            base_plus,
            variant=TARGET_NO_MAXPOS_VARIANT,
            label=f"50w trade-risk{target_risk_label} {product_label} maxpos{no_maxpos}",
            trade_risk_ratio=TARGET_TRADE_RISK_RATIO,
            maxpos=no_maxpos,
        ),
    ]

    all_summary_rows: list[dict[str, Any]] = []
    all_curve_frames: list[pd.DataFrame] = []
    all_cost_rows: list[dict[str, Any]] = []
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    activity_frames: list[pd.DataFrame] = []

    for spec in specs:
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
    checks = _checks(summary, comparison)
    decision = _decision(checks, prepared)

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

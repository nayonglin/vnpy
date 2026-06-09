from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage692_official_stage372_jd_top9_maxpos5 as s692


MODEL_TAG = "stage693_official_stage372_original_ai_plus_jd_maxpos5_v1"
OUTPUT_PREFIX = "qmt_roll_stage693_official_stage372_original_ai_plus_jd_maxpos5"
TARGET_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_maxpos5"
AI_STRATEGY = "stage693_official_stage372_original_ai_plus_jd_entry_filter"
AI_SCORE_TYPE = "stage693_fixed_add_jd_to_original_ai_pool"

GENERATED_DIR = s692.OUTPUT_DIR / "stage693_generated_inputs"


def _reconfigure_paths() -> None:
    s692.MODEL_TAG = MODEL_TAG
    s692.OUTPUT_PREFIX = OUTPUT_PREFIX
    s692.TARGET_VARIANT = TARGET_VARIANT
    s692.AI_TOP9_STRATEGY = AI_STRATEGY
    s692.AI_TOP9_SCORE_TYPE = AI_SCORE_TYPE
    s692.GENERATED_DIR = GENERATED_DIR
    s692.UNIVERSE_PLUS_JD_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
    s692.ELIGIBILITY_TOP9_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_original_ai_plus_jd_eligibility_{MODEL_TAG}.csv"
    s692.SUMMARY_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s692.COST_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    s692.COMPARISON_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    s692.ANNUAL_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
    s692.MONTHLY_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
    s692.DAILY_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    s692.POSITIONS_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
    s692.PRODUCT_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv"
    s692.PRODUCT_DELTA_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
    s692.PRODUCT_MARGIN_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
    s692.TRADE_USAGE_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
    s692.FORCED_EVENTS_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
    s692.FORCED_SUMMARY_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
    s692.AI_AUDIT_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_{MODEL_TAG}.csv"
    s692.REPORT_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s692.DECISION_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    s692.CHART_PATH = s692.OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _write_original_ai_plus_jd_eligibility(symbols: list[str]) -> pd.DataFrame:
    source = pd.read_csv(s692.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"official eligibility missing columns {sorted(missing)}")

    source_strategy = str(source["strategy"].dropna().astype(str).iloc[0])
    frame = source[source["strategy"].astype(str).eq(source_strategy)].copy()
    frame["strategy"] = AI_STRATEGY
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["score", "score_rank", "top_n"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    rows: list[pd.DataFrame] = []
    allowed = set(symbols)
    for eval_date, group in frame.groupby("eval_date", sort=True):
        group = group[group["product_vt_symbol"].astype(str).isin(allowed)].copy()
        existing = set(group["product_vt_symbol"].astype(str))
        max_rank = int(group["score_rank"].max()) if not group.empty else 0
        max_top_n = int(group["top_n"].max()) if not group.empty else 0
        min_score = float(group["score"].min()) if not group.empty else 0.0
        if s692.JD_PRODUCT not in existing:
            group["top_n"] = max_top_n + 1
            add = pd.DataFrame(
                [
                    {
                        "strategy": AI_STRATEGY,
                        "score_type": AI_SCORE_TYPE,
                        "eval_date": str(eval_date),
                        "product_vt_symbol": s692.JD_PRODUCT,
                        "score": min_score - 1e-6,
                        "score_rank": max_rank + 1,
                        "top_n": max_top_n + 1,
                    }
                ]
            )
            group = pd.concat([group, add], ignore_index=True, sort=False)
        rows.append(group)

    eligibility = pd.concat(rows, ignore_index=True, sort=False)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    eligibility.reset_index(drop=True, inplace=True)
    s692.ELIGIBILITY_TOP9_PATH.parent.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(s692.ELIGIBILITY_TOP9_PATH, index=False, encoding="utf-8-sig")
    return eligibility


def _target_spec(identity_map: str) -> s692.s653.ForcedVariant:
    base = s692._official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=TARGET_VARIANT,
        label="Stage406 official Stage372 original AI plus jd maxpos5",
        max_concurrent_positions=5,
        note=(
            "Stage693 C: keep every original official AI pool product, add jd.DCE as an extra eligible "
            "product in each monthly snapshot, and relax max_concurrent_positions from 4 to 5."
        ),
    )
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(s692.UNIVERSE_PLUS_JD_PATH),
        "max_concurrent_positions": 5,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(s692.ELIGIBILITY_TOP9_PATH),
        "ai_product_pool_strategy": AI_STRATEGY,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_original_ai_plus_jd_maxpos5")


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
    official = summary[summary["variant"].eq(s692.BASE_VARIANT)].iloc[0]
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
    jd_selected_rate = float(inputs["ai_audit"]["jd_selected"].mean() * 100.0) if not inputs["ai_audit"].empty else 0.0
    jd_pnl = 0.0
    if not product_delta.empty and "jd" in set(product_delta["product"].astype(str)):
        jd_pnl = float(product_delta[product_delta["product"].eq("jd")]["target_net_pnl"].iloc[0])

    add("return_retention_vs_official", "pass" if return_retention >= 80.0 else "fail", return_retention, ">= 80%", "原AI池+鸡蛋不能牺牲主要右尾。")
    add(
        "return_improves_vs_official",
        "pass" if not official_cmp.empty and float(official_cmp["delta"].iloc[0]) > 0.0 else "fail",
        float(official_cmp["delta"].iloc[0]) if not official_cmp.empty else 0.0,
        "> 0pp",
        "原AI池+鸡蛋+maxpos5 至少应优于当前正式版。",
    )
    add(
        "return_improves_vs_maxpos5_only",
        "pass" if not maxpos_cmp.empty and float(maxpos_cmp["delta"].iloc[0]) > 0.0 else "fail",
        float(maxpos_cmp["delta"].iloc[0]) if not maxpos_cmp.empty else 0.0,
        "> 0pp",
        "鸡蛋的边际贡献应优于只放宽 maxpos。",
    )
    add(
        "dd_not_materially_worse",
        "pass" if float(target["max_dd_pct"]) >= float(official["max_dd_pct"]) - 3.0 else "fail",
        float(target["max_dd_pct"] - official["max_dd_pct"]),
        ">= -3pp vs official",
        "最大回撤不能明显劣化。",
    )
    add("margin100", "pass" if int(target["days_over_100pct"]) == 0 else "fail", float(target["days_over_100pct"]), "0 days", "broker10 保证金不应穿100%。")
    add("2x_cost_dd40", "pass" if float(target_cost2["max_dd_pct"]) >= -40.0 else "watch", float(target_cost2["max_dd_pct"]), ">= -40%", "2x成本压力。")
    add("jd_selected_rate", "pass" if jd_selected_rate >= 99.0 else "watch", jd_selected_rate, "about 100%", "原AI池每月额外加入鸡蛋。")
    add("jd_product_pnl_positive", "pass" if jd_pnl > 0.0 else "watch", jd_pnl, "> 0", "鸡蛋自身净贡献。")

    check_frame = pd.DataFrame(checks)
    hard_fail = check_frame[check_frame["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = check_frame[check_frame["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision = "official_stage372_original_ai_plus_jd_maxpos5_rejected" if hard_fail else "official_stage372_original_ai_plus_jd_maxpos5_watch"
    return {
        "stage": "Stage406",
        "script_stage": "Stage693",
        "line_id": s692.LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": s692.BASE_VARIANT,
        "maxpos5_only": s692.MAXPOS5_VARIANT,
        "target": TARGET_VARIANT,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "added_products": [s692.JD_PRODUCT],
            "base_product_count": inputs["base_product_count"],
            "plus_product_count": inputs["plus_product_count"],
            "max_concurrent_positions_before": 4,
            "max_concurrent_positions_after": 5,
            "ai_pool_change": "keep_original_official_ai_pool_and_append_jd_each_eval_date",
            "ai_strategy": AI_STRATEGY,
            "ai_eligibility_eval_date_min": inputs["ai_eval_date_min"],
            "ai_eligibility_eval_date_max": inputs["ai_eval_date_max"],
            "ai_eligibility_eval_dates": inputs["ai_eval_dates"],
        },
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(s692.SUMMARY_PATH),
            "cost": str(s692.COST_PATH),
            "comparison": str(s692.COMPARISON_PATH),
            "annual": str(s692.ANNUAL_PATH),
            "monthly": str(s692.MONTHLY_PATH),
            "daily": str(s692.DAILY_PATH),
            "positions": str(s692.POSITIONS_PATH),
            "product": str(s692.PRODUCT_PATH),
            "product_delta": str(s692.PRODUCT_DELTA_PATH),
            "product_margin": str(s692.PRODUCT_MARGIN_PATH),
            "trade_usage": str(s692.TRADE_USAGE_PATH),
            "forced_events": str(s692.FORCED_EVENTS_PATH),
            "forced_summary": str(s692.FORCED_SUMMARY_PATH),
            "ai_audit": str(s692.AI_AUDIT_PATH),
            "report": str(s692.REPORT_PATH),
            "decision": str(s692.DECISION_PATH),
            "chart": str(s692.CHART_PATH),
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
        "# Stage693 Official Stage372 Original AI Plus jd Maxpos5",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s692.LINE_ID}`",
        "- A：当前正式版 `official_live_stage372_20w_recovery_sleeve`，`maxpos4`，正式 AI。",
        "- B：只把 `max_concurrent_positions` 从 `4` 放到 `5`，其余正式版完全不变。",
        "- C：原正式 AI 池逐月完全保留，再额外加入 `jd.DCE`，并使用 `maxpos5`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        s692._md_table(summary),
        "",
        "## Cost Stress",
        "",
        s692._md_table(cost, max_rows=120),
        "",
        "## Comparison",
        "",
        s692._md_table(comparison, max_rows=120),
        "",
        "## Annual",
        "",
        s692._md_table(annual, max_rows=80),
        "",
        "## Product Delta",
        "",
        s692._md_table(product_delta, max_rows=80),
        "",
        "## Product",
        "",
        s692._md_table(product, max_rows=120),
        "",
        "## Forced Deleverage",
        "",
        s692._md_table(forced_summary),
        "",
        "## AI Audit",
        "",
        s692._md_table(ai_audit, max_rows=80),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- hard_fail_checks: `{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks: `{', '.join(decision['watch_checks']) or '无'}`",
    ]
    s692.REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot(daily: pd.DataFrame) -> None:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s692.BASE_VARIANT: "Official maxpos4",
            s692.MAXPOS5_VARIANT: "Official maxpos5",
            TARGET_VARIANT: "Original AI + jd maxpos5",
        }
    ).fillna(data["variant"])
    colors = {
        "Official maxpos4": "#f97316",
        "Official maxpos5": "#2563eb",
        "Original AI + jd maxpos5": "#16a34a",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label"):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage406 official Stage372 original AI plus jd maxpos5")
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
    fig.savefig(s692.CHART_PATH, dpi=170)
    plt.close(fig)


def main() -> None:
    _reconfigure_paths()
    s692._write_ai_top9_eligibility = _write_original_ai_plus_jd_eligibility
    s692._target_spec = _target_spec
    s692._decision = _decision
    s692._write_report = _write_report
    s692._plot = _plot
    s692.main()


if __name__ == "__main__":
    main()

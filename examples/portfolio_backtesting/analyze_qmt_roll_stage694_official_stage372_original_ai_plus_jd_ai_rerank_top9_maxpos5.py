from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage692_official_stage372_jd_top9_maxpos5 as s692
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN


MODEL_TAG = "stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1"
OUTPUT_PREFIX = "qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5"
TARGET_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5"
AI_STRATEGY = "stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage694_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage694_official_ai_pre_full_market_coverage"

GENERATED_DIR = s692.OUTPUT_DIR / "stage694_generated_inputs"

_ORIGINAL_DECISION = s692._decision


def _reconfigure_paths() -> None:
    s692.MODEL_TAG = MODEL_TAG
    s692.OUTPUT_PREFIX = OUTPUT_PREFIX
    s692.TARGET_VARIANT = TARGET_VARIANT
    s692.AI_TOP_N = 9
    s692.AI_TOP9_STRATEGY = AI_STRATEGY
    s692.AI_TOP9_SCORE_TYPE = AI_SCORE_TYPE
    s692.AI_TOP9_OFFICIAL_PRE2022_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s692.GENERATED_DIR = GENERATED_DIR
    s692.UNIVERSE_PLUS_JD_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
    s692.ELIGIBILITY_TOP9_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_original_ai_plus_jd_rerank_top9_eligibility_{MODEL_TAG}.csv"
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


def _official_pre_full_market_rows(first_full_market_eval: str) -> pd.DataFrame:
    official = pd.read_csv(s692.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
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
    official["strategy"] = AI_STRATEGY
    official["score_type"] = AI_PRE_COVERAGE_SCORE_TYPE
    for column in ["score", "score_rank", "top_n"]:
        official[column] = pd.to_numeric(official[column], errors="coerce").fillna(0.0)
    official["top_n"] = official.groupby("eval_date")["product_vt_symbol"].transform("count")
    return official[list(required)].copy()


def _write_original_ai_plus_jd_rerank_top9_eligibility(symbols: list[str]) -> pd.DataFrame:
    official = pd.read_csv(s692.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(official.columns)
    if missing:
        raise ValueError(f"official eligibility missing columns {sorted(missing)}")

    official["eval_date"] = pd.to_datetime(official["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    source_strategy = str(official["strategy"].dropna().astype(str).iloc[0])
    official = official[official["strategy"].astype(str).eq(source_strategy)].copy()
    official = official[official["product_vt_symbol"].astype(str).isin(set(symbols))].copy()

    predictions = pd.read_csv(
        s692.FULL_MARKET_AI_PREDICTIONS_PATH,
        usecols=["eval_date", "product_vt_symbol", PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN],
    )
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    predictions["product_vt_symbol"] = predictions["product_vt_symbol"].astype(str)
    predictions = predictions[predictions["product_vt_symbol"].isin(set(symbols))].copy()
    if predictions.empty:
        raise RuntimeError("no full-market AI prediction rows for original-ai-plus-jd universe")

    first_full_market_eval = str(predictions["eval_date"].min())
    pre_rows = _official_pre_full_market_rows(first_full_market_eval)
    pred_by_date = {date: frame.copy() for date, frame in predictions.groupby("eval_date", sort=False)}

    rows: list[dict[str, Any]] = []
    missing_prediction_rows: list[dict[str, Any]] = []
    for eval_date, official_group in official.groupby("eval_date", sort=True):
        eval_date = str(eval_date)
        if eval_date < first_full_market_eval:
            continue
        candidates = set(official_group["product_vt_symbol"].astype(str)) | {s692.JD_PRODUCT}
        pred_group = pred_by_date.get(eval_date, pd.DataFrame(columns=predictions.columns))
        pred_group = pred_group[pred_group["product_vt_symbol"].isin(candidates)].copy()
        missing_candidates = sorted(candidates - set(pred_group["product_vt_symbol"].astype(str)))
        if missing_candidates:
            missing_prediction_rows.append(
                {
                    "eval_date": eval_date,
                    "missing_candidates": ",".join(missing_candidates),
                    "missing_count": len(missing_candidates),
                }
            )
        if pred_group.empty:
            continue
        ranked = pred_group.sort_values(
            [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN, "product_vt_symbol"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        ranked["score_rank"] = range(1, len(ranked) + 1)
        selected = ranked.head(s692.AI_TOP_N).copy()
        for row in selected.itertuples(index=False):
            rows.append(
                {
                    "strategy": AI_STRATEGY,
                    "score_type": AI_SCORE_TYPE,
                    "eval_date": eval_date,
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "score": float(getattr(row, PROBABILITY_COLUMN)),
                    "score_rank": int(getattr(row, "score_rank")),
                    "top_n": s692.AI_TOP_N,
                }
            )

    reranked = pd.DataFrame(rows)
    if reranked.empty:
        raise RuntimeError("AI rerank produced no eligibility rows")
    eligibility = pd.concat([pre_rows, reranked], ignore_index=True, sort=False)
    eligibility.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    eligibility.reset_index(drop=True, inplace=True)
    s692.ELIGIBILITY_TOP9_PATH.parent.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(s692.ELIGIBILITY_TOP9_PATH, index=False, encoding="utf-8-sig")

    if missing_prediction_rows:
        missing_path = GENERATED_DIR / f"{OUTPUT_PREFIX}_missing_prediction_candidates_{MODEL_TAG}.csv"
        pd.DataFrame(missing_prediction_rows).to_csv(missing_path, index=False, encoding="utf-8-sig")
    return eligibility


def _target_spec(identity_map: str) -> s692.s653.ForcedVariant:
    base = s692._official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=TARGET_VARIANT,
        label="Stage407 official Stage372 original AI plus jd AI rerank top9 maxpos5",
        max_concurrent_positions=5,
        note=(
            "Stage694 C: each monthly candidate set is the official AI-selected products plus jd.DCE; "
            "full-market AI scores rerank only that restricted set and keep top9, with maxpos5."
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
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5")


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    product_delta: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    decision = _ORIGINAL_DECISION(summary, cost, comparison, product_delta, inputs)
    hard_fail = list(decision.get("hard_fail_checks", []))
    decision["stage"] = "Stage407"
    decision["script_stage"] = "Stage694"
    decision["model_tag"] = MODEL_TAG
    decision["target"] = TARGET_VARIANT
    decision["decision"] = (
        "official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_rejected"
        if hard_fail
        else "official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_watch"
    )
    change = dict(decision.get("change", {}))
    change.update(
        {
            "ai_pool_change": "restrict_each_eval_date_to_original_official_ai_products_plus_jd_then_ai_rerank_top9",
            "ai_top_n": s692.AI_TOP_N,
            "ai_strategy": AI_STRATEGY,
            "full_market_prediction_coverage_caveat": (
                "Full-market AI predictions start at 2022-01-28. Earlier eval dates keep official eligibility, "
                "so jd.DCE does not participate before prediction coverage exists."
            ),
        }
    )
    decision["change"] = change
    return decision


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s692.BASE_VARIANT: "Official maxpos4",
            s692.MAXPOS5_VARIANT: "Official maxpos5",
            TARGET_VARIANT: "Original AI + jd AI rerank top9 maxpos5",
        }
    ).fillna(data["variant"])
    colors = {
        "Official maxpos4": "#f97316",
        "Official maxpos5": "#2563eb",
        "Original AI + jd AI rerank top9 maxpos5": "#16a34a",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label"):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage407 official Stage372 original AI plus jd AI rerank top9 maxpos5")
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
        "# Stage407 Official Stage372 Original AI + jd AI Rerank Top9 Maxpos5",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s692.LINE_ID}`",
        "- A：当前正式版 `official_live_stage372_20w_recovery_sleeve`，`maxpos4`，正式 AI。",
        "- B：只把 `max_concurrent_positions` 从 `4` 放到 `5`，其余正式版完全不变。",
        "- C：每月候选集限定为“正式 AI 当月原选中产品 + `jd.DCE`”，再用 AI 预测分数重排取 `top9`，并使用 `maxpos5`。",
        "- 2020-2021 因 full-market AI 预测未覆盖，沿用正式 AI 快照且不放行鸡蛋。",
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


def main() -> None:
    _reconfigure_paths()
    s692._write_ai_top9_eligibility = _write_original_ai_plus_jd_rerank_top9_eligibility
    s692._target_spec = _target_spec
    s692._decision = _decision
    s692._plot = _plot
    s692._write_report = _write_report
    s692.main()


if __name__ == "__main__":
    main()

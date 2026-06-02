from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage521_stage520_robustness_audit as s521  # noqa: E402


MODEL_TAG = "stage527_stage526_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage527_stage526_robustness_audit"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

STAGE526_SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"
STAGE526_COST_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_cost_stress_{STAGE526_TAG}.csv"
STAGE526_MARGIN_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE520_SUMMARY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_summary_{STAGE520_TAG}.csv"
STAGE520_COST_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_cost_stress_{STAGE520_TAG}.csv"
STAGE520_MARGIN_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HOLDING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_holding_experience_{MODEL_TAG}.csv"
COLD_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cold_start_{MODEL_TAG}.csv"
EXTRA_CASH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_cash_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CANDIDATE = "r080_pc25_maxpos4"
REFERENCES = ("r080_pc25_u75", "r070_pc30_u75", "r080_pc30_u80")
ALL_VARIANTS = (CANDIDATE, *REFERENCES)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.concat(
        [
            pd.read_csv(STAGE526_SUMMARY_IN, encoding="utf-8-sig"),
            pd.read_csv(STAGE520_SUMMARY_IN, encoding="utf-8-sig"),
        ],
        ignore_index=True,
        sort=False,
    )
    cost = pd.concat(
        [
            pd.read_csv(STAGE526_COST_IN, encoding="utf-8-sig"),
            pd.read_csv(STAGE520_COST_IN, encoding="utf-8-sig"),
        ],
        ignore_index=True,
        sort=False,
    )
    margin = pd.concat(
        [
            pd.read_csv(STAGE526_MARGIN_IN, encoding="utf-8-sig"),
            pd.read_csv(STAGE520_MARGIN_IN, encoding="utf-8-sig"),
        ],
        ignore_index=True,
        sort=False,
    )
    summary = summary[summary["variant"].isin(ALL_VARIANTS)].drop_duplicates("variant").copy()
    cost = cost[cost["variant"].isin(ALL_VARIANTS)].copy()
    margin = margin[margin["variant"].isin(ALL_VARIANTS)].copy()
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    return summary, cost, margin


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, holding: pd.DataFrame, cold: pd.DataFrame) -> dict[str, Any]:
    summary_map = summary.drop_duplicates("variant").set_index("variant").to_dict(orient="index")
    cost_map = cost.set_index(["variant", "cost_multiplier"]).to_dict(orient="index")
    cand = summary_map.get(CANDIDATE, {})
    cand2 = cost_map.get((CANDIDATE, 2.0), {})
    cand3 = cost_map.get((CANDIDATE, 3.0), {})
    h63 = holding[(holding["variant"].eq(CANDIDATE)) & (holding["holding_days"].eq(63))]
    h126 = holding[(holding["variant"].eq(CANDIDATE)) & (holding["holding_days"].eq(126))]
    cold_cand = cold[cold["variant"].eq(CANDIDATE)]
    hard = bool(
        int(cand.get("dd40_pass", 0)) == 1
        and int(cand.get("broker10_100_pass", 0)) == 1
        and _safe_float(cand2.get("max_dd_pct")) >= -40.0
    )
    robust = bool(
        hard
        and _safe_float(cold_cand["dd40_pass_rate_pct"].min() if not cold_cand.empty else 0.0) >= 100.0
        and _safe_float(cold_cand["broker100_pass_rate_pct"].min() if not cold_cand.empty else 0.0) >= 100.0
        and _safe_float(h63["dd40_breach_rate_pct"].iloc[0] if not h63.empty else 100.0) <= 0.0
        and _safe_float(h126["dd40_breach_rate_pct"].iloc[0] if not h126.empty else 100.0) <= 0.0
    )
    if robust and _safe_float(cand.get("return_retention_vs_stage079_pct")) >= 70.0:
        label = "stage526_candidate_survives_robustness_promote_to_next_review"
    elif hard:
        label = "stage526_candidate_hard_pass_but_robustness_gap"
    else:
        label = "stage526_candidate_fails_robustness"
    return {
        "decision": label,
        "candidate": cand,
        "candidate_2x": cand2,
        "candidate_3x": cand3,
        "candidate_holding_63d": h63.to_dict(orient="records"),
        "candidate_holding_126d": h126.to_dict(orient="records"),
        "candidate_cold_start": cold_cand.to_dict(orient="records"),
        "reference_summary": {variant: summary_map.get(variant, {}) for variant in REFERENCES},
    }


def _plot(margin: pd.DataFrame, summary: pd.DataFrame, holding: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_equity, ax_margin, ax_scatter, ax_hold = axes.flatten()
    colors = ["#dc2626", "#2563eb", "#0f766e", "#7c3aed"]
    color_map = {variant: colors[index % len(colors)] for index, variant in enumerate(ALL_VARIANTS)}
    for variant, frame in margin.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        ax_equity.plot(frame["date"], frame["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        ax_margin.plot(frame["date"], frame["broker10_margin_to_equity_pct"], label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_equity.set_title("账户权益")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_margin.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax_margin.set_title("broker10保证金/权益")
    ax_margin.set_ylabel("%")
    ax_margin.grid(alpha=0.25)

    ax_scatter.scatter(
        summary["return_retention_vs_stage079_pct"],
        summary["max_broker10_margin_to_equity_pct"],
        s=np.maximum(summary["total_return_pct"], 1.0) / 18.0,
        c=[color_map.get(v, "#64748b") for v in summary["variant"]],
        alpha=0.85,
    )
    for row in summary.itertuples(index=False):
        ax_scatter.annotate(str(row.variant), (row.return_retention_vs_stage079_pct, row.max_broker10_margin_to_equity_pct), fontsize=8)
    ax_scatter.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.set_title("收益保留 vs 保证金")
    ax_scatter.set_xlabel("相对Stage079收益保留%")
    ax_scatter.set_ylabel("最大broker10保证金/权益%")
    ax_scatter.grid(alpha=0.25)

    h = holding[holding["holding_days"].isin([63, 126])].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct").reindex(ALL_VARIANTS)
    pivot.plot(kind="bar", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.set_title("3个月/6个月 p05收益")
    ax_hold.set_ylabel("%")
    ax_hold.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, holding: pd.DataFrame, cold: pd.DataFrame, extra: pd.DataFrame, decision: dict[str, Any]) -> None:
    view = summary[
        [
            "variant",
            "end_equity",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
        ]
    ].copy()
    cost_view = cost[cost["cost_multiplier"].isin([2.0, 3.0])][["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "max_broker10_margin_to_equity_pct"]]
    hold_view = holding[holding["holding_days"].isin([63, 126, 252, 504])][
        [
            "variant",
            "holding_days",
            "p05_return_pct",
            "median_return_pct",
            "dd30_breach_rate_pct",
            "dd40_breach_rate_pct",
            "broker100_breach_rate_pct",
        ]
    ]
    cold_view = cold[["variant", "start_type", "sample_count", "worst_max_dd_pct", "dd40_pass_rate_pct", "broker100_pass_rate_pct"]]
    lines = [
        "# Stage527 Stage526候选鲁棒性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：固定候选只读鲁棒性审计；不重跑策略、不改参数。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## 总览",
        "",
        _md_table(view),
        "",
        "## 成本压力",
        "",
        _md_table(cost_view),
        "",
        "## 任意持有体验",
        "",
        _md_table(hold_view, max_rows=24),
        "",
        "## 冷启动",
        "",
        _md_table(cold_view),
        "",
        "## 额外现金",
        "",
        _md_table(extra),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    summary, cost, margin = _load()
    holding = s521._holding_experience(margin)
    cold = s521._cold_start(margin)
    extra = s521._extra_cash(margin)
    decision = _decision(summary, cost, holding, cold)
    _plot(margin, summary, holding)
    _write_report(summary, cost, holding, cold, extra, decision)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    holding.to_csv(HOLDING_PATH, index=False, encoding="utf-8-sig")
    cold.to_csv(COLD_START_PATH, index=False, encoding="utf-8-sig")
    extra.to_csv(EXTRA_CASH_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

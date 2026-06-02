from __future__ import annotations

from dataclasses import dataclass
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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402


MODEL_TAG = "stage526_productcap25_breadth_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_events_{MODEL_TAG}.csv"
PRODUCT_EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_events_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    overrides: dict[str, Any]
    note: str


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


def _variants(identity_map: str) -> tuple[VariantSpec, ...]:
    pc25 = s519._product_cap_overrides(0.25, identity_map)
    pc30 = s519._product_cap_overrides(0.30, identity_map)
    return (
        VariantSpec(
            "r080_pc30_maxpos4_ref",
            "risk080 pc30 + maxpos4 reference",
            0.80,
            {**pc30, "max_concurrent_positions": 4},
            "Stage524 近通过参考。",
        ),
        VariantSpec(
            "r080_pc25_control",
            "risk080 product cap25 control",
            0.80,
            pc25,
            "单产品 cap25，不加 usage，不加持仓广度限制。",
        ),
        VariantSpec(
            "r080_pc25_maxpos5",
            "risk080 pc25 + max active products 5",
            0.80,
            {**pc25, "max_concurrent_positions": 5},
            "cap25 叠加最大活跃产品5。",
        ),
        VariantSpec(
            "r080_pc25_maxpos4",
            "risk080 pc25 + max active products 4",
            0.80,
            {**pc25, "max_concurrent_positions": 4},
            "cap25 叠加最大活跃产品4，测试能否无现金消灭最后尖峰。",
        ),
    )


def _summary_and_cost(combo_daily: pd.DataFrame, specs: tuple[VariantSpec, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec_map = {spec.variant: spec for spec in specs}
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(frame, cost_multiplier)
            row = s516._metrics_from_equity(equity, frame, variant=variant, label=spec.label, cost_multiplier=cost_multiplier)
            row.update({"risk_multiplier": spec.risk_multiplier, "note": spec.note})
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    ranked: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        variant = str(item["variant"])
        two = cost2.loc[variant] if variant in cost2.index else None
        two_x_dd = _safe_float(two["max_dd_pct"]) if two is not None else 0.0
        hard_pass = int(
            int(item["dd40_pass"]) == 1
            and int(item["broker10_100_pass"]) == 1
            and two is not None
            and two_x_dd >= -40.0
        )
        retention = _safe_float(item["return_retention_vs_stage079_pct"])
        score = retention - max(0.0, 65.0 - retention) - max(0.0, _safe_float(item["max_broker10_margin_to_equity_pct"]) - 100.0) * 3.0
        ranked.append({**item, "two_x_max_dd_pct": two_x_dd, "hard_pass": hard_pass, "retention65_pass": int(retention >= 65.0), "decision_score": score})
    ranked = sorted(ranked, key=lambda item: (item["hard_pass"], item["retention65_pass"], item["decision_score"]), reverse=True)
    hard65 = [item for item in ranked if item["hard_pass"] and item["retention65_pass"]]
    if hard65:
        decision = "productcap25_breadth_candidate_found"
    elif any(item["hard_pass"] for item in ranked):
        decision = "productcap25_breadth_hard_pass_but_retention_low"
    else:
        decision = "productcap25_breadth_not_ready"
    return {"decision": decision, "best_variant": ranked[0] if ranked else {}, "hard_pass_variants": [x for x in ranked if x["hard_pass"]], "ranked": ranked}


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame, cost: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_equity, ax_margin, ax_scatter, ax_cost = axes.flatten()
    colors = ["#0f766e", "#2563eb", "#7c3aed", "#dc2626"]
    color_map = {variant: colors[index % len(colors)] for index, variant in enumerate(summary["variant"].tolist())}
    for variant, frame in combo_daily.groupby("variant", sort=False):
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
    ax_scatter.axvline(65, color="#64748b", linestyle=":", linewidth=1)
    ax_scatter.set_title("收益保留 vs 保证金")
    ax_scatter.set_xlabel("相对Stage079收益保留%")
    ax_scatter.set_ylabel("最大broker10保证金/权益%")
    ax_scatter.grid(alpha=0.25)
    cost2 = cost[cost["cost_multiplier"].eq(2.0)]
    ax_cost.barh(cost2["variant"], cost2["max_dd_pct"], color=[color_map.get(v, "#64748b") for v in cost2["variant"]])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("2x成本最大回撤")
    ax_cost.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct", "total_return_pct"]].copy()
    view = summary.merge(cost2, on="variant", suffixes=("", "_2x"))[
        [
            "variant",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "max_dd_pct_2x",
        ]
    ].sort_values("return_retention_vs_stage079_pct", ascending=False)
    rolling_view = rolling[rolling["holding_days"].isin([63, 126])][
        ["variant", "holding_days", "p05_return_pct", "median_return_pct", "min_window_dd_pct", "positive_rate_pct"]
    ]
    lines = [
        "# Stage526 cap25 + 活跃产品广度前沿",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：A/C粗前沿；不改alpha、不改入场/出场、不做日期或品种补丁。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## 总览",
        "",
        _md_table(view),
        "",
        "## 3个月/6个月持有体验",
        "",
        _md_table(rolling_view, max_rows=16),
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"[stage526] running {spec.variant}", flush=True)
        daily, positions, _usage = s517._run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
    c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = s517._combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily, specs)
    rolling = s516._rolling_holding(combo_daily)
    events, product_events = s516._event_days(combo_daily, product_margin)
    decision = _decision(summary, cost)
    _plot(combo_daily, summary, cost)
    _write_report(summary, cost, rolling, decision)

    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_events.to_csv(PRODUCT_EVENT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

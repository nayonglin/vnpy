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
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import RISK_CLUSTER_MAP  # noqa: E402


MODEL_TAG = "stage519_product_margin_cap_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage519_product_margin_cap_frontier"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
C3_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c3_daily_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
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


def _product_identity_cluster_map(metadata: dict[str, Any]) -> str:
    products = sorted({s513._product_from_contract(symbol) for symbol in metadata["vt_symbols"] if "." in str(symbol)})
    rows: set[str] = set()
    for product in products:
        if not product or "." not in product:
            continue
        symbol, exchange = product.split(".", 1)
        rows.add(f"{product}={product}")
        rows.add(f"{symbol.lower()}.{exchange.upper()}={product}")
    return ",".join(sorted(rows))


def _product_cap_overrides(ratio: float, identity_map: str) -> dict[str, Any]:
    return {
        "enable_risk_cluster_margin_cap": True,
        "risk_cluster_margin_cap_ratio": float(ratio),
        "risk_cluster_target_clusters": "",
        "risk_cluster_map": identity_map,
    }


def _broad_cluster_cap_overrides(ratio: float) -> dict[str, Any]:
    return {
        "enable_risk_cluster_margin_cap": True,
        "risk_cluster_margin_cap_ratio": float(ratio),
        "risk_cluster_target_clusters": "",
        "risk_cluster_map": RISK_CLUSTER_MAP,
    }


def _variants(identity_map: str) -> tuple[VariantSpec, ...]:
    return (
        VariantSpec(
            "r060_legacy_nocap_control",
            "risk060 legacy no-cap control",
            0.60,
            {},
            "Stage214/217 risk060 对照。",
        ),
        VariantSpec(
            "r070_legacy_nocap_control",
            "risk070 legacy no-cap control",
            0.70,
            {},
            "Stage214/217 risk070 高收益高保证金对照。",
        ),
        VariantSpec(
            "r070_broadcluster35",
            "risk070 broad-cluster cap35",
            0.70,
            _broad_cluster_cap_overrides(0.35),
            "Stage217 最优弱形状复刻：按风险簇合并限制 35%。",
        ),
        VariantSpec(
            "r070_productcap35",
            "risk070 product cap35",
            0.70,
            _product_cap_overrides(0.35, identity_map),
            "每个产品独立作为保证金簇，单产品 cap=35%。",
        ),
        VariantSpec(
            "r070_productcap30",
            "risk070 product cap30",
            0.70,
            _product_cap_overrides(0.30, identity_map),
            "每个产品独立作为保证金簇，单产品 cap=30%。",
        ),
        VariantSpec(
            "r070_productcap25",
            "risk070 product cap25",
            0.70,
            _product_cap_overrides(0.25, identity_map),
            "每个产品独立作为保证金簇，单产品 cap=25%。",
        ),
        VariantSpec(
            "r080_productcap30",
            "risk080 product cap30",
            0.80,
            _product_cap_overrides(0.30, identity_map),
            "提高风险预算后用单产品 cap30 限制名义集中。",
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
            row = s516._metrics_from_equity(
                equity,
                frame,
                variant=variant,
                label=spec.label,
                cost_multiplier=cost_multiplier,
            )
            row.update(
                {
                    "risk_multiplier": spec.risk_multiplier,
                    "note": spec.note,
                }
            )
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
        hard_pass = bool(
            int(item["dd40_pass"]) == 1
            and int(item["broker10_100_pass"]) == 1
            and two is not None
            and two_x_dd >= -40.0
        )
        score = (
            _safe_float(item["return_retention_vs_stage079_pct"])
            - max(0.0, _safe_float(item["max_broker10_margin_to_equity_pct"]) - 100.0) * 2.0
            - max(0.0, -40.0 - two_x_dd) * 3.0
        )
        ranked.append(
            {
                **item,
                "two_x_max_dd_pct": two_x_dd,
                "hard_pass": int(hard_pass),
                "decision_score": score,
            }
        )
    ranked = sorted(ranked, key=lambda item: (item["hard_pass"], item["decision_score"]), reverse=True)
    hard = [item for item in ranked if item["hard_pass"]]
    return {
        "decision": "product_margin_cap_candidate_found" if hard else "product_margin_cap_not_ready",
        "best_variant": ranked[0] if ranked else {},
        "hard_pass_variants": hard,
        "ranked": ranked,
        "pass_definition": "DD40 + broker10<=100 + 2x成本DD40",
    }


def _plot(summary: pd.DataFrame, cost: pd.DataFrame, combo_daily: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_nav, ax_margin, ax_scatter, ax_cost = axes.flatten()
    color_map = {
        "r060_legacy_nocap_control": "#2563eb",
        "r070_legacy_nocap_control": "#dc2626",
        "r070_broadcluster35": "#059669",
        "r070_productcap35": "#f97316",
        "r070_productcap30": "#7c3aed",
        "r070_productcap25": "#0891b2",
        "r080_productcap30": "#be123c",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        label = str(frame["label"].iloc[0])
        ax_nav.plot(frame["date"], frame["account_equity"], label=label, linewidth=0.9, color=color_map.get(variant))
        ax_margin.plot(
            frame["date"],
            frame["broker10_margin_to_equity_pct"],
            label=label,
            linewidth=0.9,
            color=color_map.get(variant),
        )
    ax_nav.set_title("账户权益")
    ax_nav.grid(alpha=0.25)
    ax_nav.legend(fontsize=6)
    ax_margin.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax_margin.set_title("broker10保证金/权益")
    ax_margin.set_ylabel("%")
    ax_margin.grid(alpha=0.25)

    ax_scatter.scatter(
        summary["return_retention_vs_stage079_pct"],
        summary["max_broker10_margin_to_equity_pct"],
        s=np.maximum(summary["total_return_pct"], 1.0) / 20.0,
        c=[color_map.get(v, "#64748b") for v in summary["variant"]],
        alpha=0.8,
    )
    for row in summary.itertuples(index=False):
        ax_scatter.annotate(str(row.variant).replace("_", "\n"), (row.return_retention_vs_stage079_pct, row.max_broker10_margin_to_equity_pct), fontsize=7)
    ax_scatter.axhline(100, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.set_title("收益保留 vs 保证金")
    ax_scatter.set_xlabel("相对Stage079收益保留%")
    ax_scatter.set_ylabel("最大broker10保证金/权益%")
    ax_scatter.grid(alpha=0.25)

    cost2 = cost[cost["cost_multiplier"].eq(2.0)].copy()
    ax_cost.barh(cost2["variant"], cost2["max_dd_pct"], color=[color_map.get(v, "#64748b") for v in cost2["variant"]])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("2x成本最大回撤")
    ax_cost.set_xlabel("%")
    ax_cost.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, window: pd.DataFrame, decision: dict[str, Any]) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct", "total_return_pct", "days_over_100pct"]].copy()
    merged = summary.merge(cost2, on="variant", suffixes=("", "_2x"))
    view = merged[
        [
            "variant",
            "total_return_pct",
            "return_retention_vs_stage079_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "max_dd_pct_2x",
            "total_slippage",
            "total_trade_count",
        ]
    ].copy()
    worst_window = (
        window.sort_values(["variant", "window_max_broker10_margin_to_equity_pct"], ascending=[True, False])
        .groupby("variant")
        .head(1)
        if not window.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage519 单产品保证金上限前沿",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：A/C 部署层结构实验；不修改 C3/Stage079/Stage103/xsmom alpha。",
        "- 候选假设：超限日通常由第一大产品触发，但第一大产品会轮换；因此测试单产品保证金 cap，而不是产品黑名单。",
        f"- 硬通过定义：`{decision['pass_definition']}`。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 外部调研判断",
        "",
        "- Managed futures 的低相关分散是有效先验，但本线历史实验说明净值层低相关不等于真实资金可执行。",
        "- 清算/券商保证金是真实硬约束，公开框架或价差范式不能替代本账户 exact position margin；本阶段继续使用 broker10 上浮硬闸门。",
        "- 本轮不使用品种黑名单；产品 cap 是账户层资金集中约束，属于可预声明、低自由度部署结构。",
        "",
        "## 核心结果",
        "",
        _md_table(view),
        "",
        "## 最差保证金窗口",
        "",
        _md_table(
            worst_window[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ]
            if not worst_window.empty
            else pd.DataFrame()
        ),
        "",
        "## 判断",
        "",
        f"- 最优排序：`{decision.get('best_variant', {}).get('variant', '')}`。",
        "- 若无硬通过版本，则不继续扫 `34/33/32%` 这类小数；下一步只允许做结构更不同的低保证金收益源，或在本次结果特别接近时做一次预声明的机制消融。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = _product_identity_cluster_map(metadata)
    specs = _variants(identity_map)
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"running {spec.variant} ...", flush=True)
        daily, positions, _usage = s517._run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
    c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    c3_margin_daily, product_margin = s513._position_margin(positions_all, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = s517._combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily, specs)
    window = s516._window_metrics(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    events, product_events = s516._event_days(combo_daily, product_margin)
    decision = _decision(summary, cost)
    _plot(summary, cost, combo_daily)

    c3_daily.to_csv(C3_DAILY_PATH, index=False, encoding="utf-8-sig")
    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_events.to_csv(PRODUCT_EVENT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, cost, window, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

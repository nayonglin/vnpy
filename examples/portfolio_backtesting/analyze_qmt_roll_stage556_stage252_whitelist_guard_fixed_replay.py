from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551
import analyze_qmt_roll_stage552_dynamic_annual_selector_sleeve as s552


MODEL_TAG = "stage556_stage252_whitelist_guard_fixed_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage556_stage252_whitelist_guard_fixed_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"
SNAPSHOT_PATH: Path | None = None

TOP6_SPEC = s552.DynamicSpec(
    "dynamic_prevtop6_r050_pc15_maxpos3",
    "prev_year_top6",
    "Stage526 + fixed annual prev-year top6 sleeve r050 pc15 maxpos3",
    0.50,
    0.15,
    3,
    0.35,
    "Stage256修复语义：年度白名单同日生效，并覆盖flat/reverse/add新增风险路径；已有持仓换月自然延续。",
)


def _retarget_stage552_outputs() -> None:
    s552.MODEL_TAG = MODEL_TAG
    s552.OUTPUT_PREFIX = OUTPUT_PREFIX
    s552.SPECS = (TOP6_SPEC,)
    output_dir = s552.OUTPUT_DIR
    path_names = {
        "UNIVERSE_PATH": "noncore_commodity_universe",
        "ELIGIBILITY_PATH": "annual_eligibility",
        "SUMMARY_PATH": "summary",
        "COST_PATH": "cost_stress",
        "ROLLING_PATH": "rolling_holding",
        "WINDOW_PATH": "window_metrics",
        "COMBINED_DAILY_PATH": "combined_daily",
        "SATELLITE_DAILY_PATH": "satellite_daily",
        "POSITIONS_PATH": "positions",
        "SATELLITE_MARGIN_PATH": "satellite_margin_daily",
        "SATELLITE_PRODUCT_PATH": "satellite_product_harvest",
        "SATELLITE_SUMMARY_PATH": "satellite_standalone",
        "SELECTION_AUDIT_PATH": "annual_selection",
        "ENTRY_SUMMARY_PATH": "entry_summary",
        "DECISION_PATH": "decision",
        "REPORT_PATH": "report",
        "CHART_PATH": "chart",
    }
    for attr, stem in path_names.items():
        suffix = ".json" if attr == "DECISION_PATH" else ".md" if attr == "REPORT_PATH" else ".png" if attr == "CHART_PATH" else ".csv"
        setattr(s552, attr, output_dir / f"{OUTPUT_PREFIX}_{stem}_{MODEL_TAG}{suffix}")
    global SNAPSHOT_PATH
    SNAPSHOT_PATH = output_dir / f"{OUTPUT_PREFIX}_entry_snapshots_{MODEL_TAG}.csv"


def _entry_summary_with_raw_snapshots(snapshots: pd.DataFrame) -> pd.DataFrame:
    if SNAPSHOT_PATH is not None:
        snapshots.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    return s551._ORIGINAL_STAGE556_ENTRY_SUMMARY(snapshots)


def _sleeve_overrides_with_next_trade_date(spec: s552.DynamicSpec, identity_map: str) -> dict[str, Any]:
    overrides = s552._ORIGINAL_STAGE556_SLEEVE_OVERRIDES(spec, identity_map)
    overrides["ai_product_pool_use_next_trade_date_for_entry"] = True
    return overrides


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    satellite_summary: pd.DataFrame,
) -> dict[str, Any]:
    decision = s551._decision(summary, cost, rolling, satellite_summary)
    wide_decision = decision.get("decision", "")
    ranked = decision.get("ranked", [])
    best = next((item for item in ranked if item.get("variant") == TOP6_SPEC.variant), {})
    strict_materiality_pass = bool(
        best
        and float(best.get("return_vs_stage526_pct", 0.0) or 0.0) >= 100.5
        and float(best.get("holding63_p05_improvement_pp", 0.0) or 0.0) >= 0.5
        and float(best.get("holding126_p05_improvement_pp", 0.0) or 0.0) >= 0.5
        and float(best.get("satellite_total_pnl", 0.0) or 0.0) >= 115000.0
    )
    decision["stage"] = "Stage256"
    decision["model_tag"] = MODEL_TAG
    decision["line_id"] = LINE_ID
    decision["candidate_under_audit"] = TOP6_SPEC.variant
    decision["decision"] = (
        "fixed_whitelist_guard_replay_strict_materiality_pass_next_audit"
        if strict_materiality_pass
        else "fixed_whitelist_guard_replay_materiality_insufficient_keep_paper_only"
    )
    decision["wide_stage552_decision"] = wide_decision
    decision["strict_materiality_pass"] = int(strict_materiality_pass)
    decision["execution_semantics"] = (
        "年度白名单按预计下一交易日成交窗口重验，eval_date 当天生效；"
        "flat/reverse/add 等新增产品风险路径都必须通过成交窗口所属白名单；"
        "rollover_reopen 只作为已有持仓换月自然延续，不强行年初平仓。"
    )
    decision["guard_fix"] = {
        "eval_date_search": "searchsorted side=right, eval_date inclusive",
        "entry_effective_date": "next trade date when ai_product_pool_use_next_trade_date_for_entry=True",
        "flat_entry": "already guarded by ai_product_pool",
        "reverse_entry": "guarded in Stage256",
        "regular_add": "guarded in Stage256",
        "donchian_add": "guarded in Stage256",
        "rollover_reopen": "allowed as carry continuation",
    }
    decision["next_step"] = (
        "若修复后无非白名单新开/加仓且材料性仍弱，停止年度top6历史回测路线；"
        "若意外保留材料性，再做一次 Stage255 同口径语义/材料性审计。"
    )
    return decision


def _plot(
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    combo_daily: pd.DataFrame,
    satellite_daily: pd.DataFrame,
    product_harvest: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_equity, ax_delta, ax_hold, ax_cost = axes.flatten()
    colors = {s552.CONTROL: "#111827", TOP6_SPEC.variant: "#7c3aed"}

    pivot = combo_daily[combo_daily["variant"].isin([s552.CONTROL, TOP6_SPEC.variant])].copy()
    for variant, frame in pivot.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(
            pd.to_datetime(ordered["date"]),
            ordered["account_equity"],
            label=variant,
            linewidth=0.9,
            color=colors.get(variant),
        )
    ax_equity.set_title("账户权益：Stage256 白名单修复重放")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=8)

    equity_pivot = pivot.pivot(index="date", columns="variant", values="account_equity")
    if s552.CONTROL in equity_pivot and TOP6_SPEC.variant in equity_pivot:
        delta = equity_pivot[TOP6_SPEC.variant] - equity_pivot[s552.CONTROL]
        ax_delta.plot(pd.to_datetime(delta.index), delta.values, color="#7c3aed", linewidth=0.9)
    ax_delta.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_delta.set_title("账户权益差：修复后top6 - Stage526")
    ax_delta.grid(alpha=0.25)

    hold = rolling[rolling["holding_days"].isin([63, 126])].copy()
    hold_pivot = hold.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    hold_pivot = hold_pivot.reindex([s552.CONTROL, TOP6_SPEC.variant])
    hold_pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("任意启动3/6个月 p05收益")
    ax_hold.grid(axis="x", alpha=0.25)

    cost_pivot = cost.pivot(index="variant", columns="cost_multiplier", values="max_dd_pct")
    cost_pivot = cost_pivot.reindex([s552.CONTROL, TOP6_SPEC.variant])
    cost_pivot.plot(kind="barh", ax=ax_cost, color=["#0f172a", "#ea580c", "#b91c1c"])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("1x/2x/3x成本压力最大回撤")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage256 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(s552.CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    window: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    selection_audit: pd.DataFrame,
    product_harvest: pd.DataFrame,
    entry_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    ranked = pd.DataFrame(decision.get("ranked", []))
    view = summary.copy()
    if not ranked.empty:
        view = view.merge(
            ranked[
                [
                    "variant",
                    "holding63_p05_improvement_pp",
                    "holding126_p05_improvement_pp",
                    "satellite_total_pnl",
                    "soft_score",
                ]
            ],
            on="variant",
            how="left",
        )
    lines = [
        "# Stage256 Stage252 白名单闸门修复重放",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        f"- A：`{s552.CONTROL}`。",
        f"- C：`{TOP6_SPEC.variant}`。",
        "- 阶段性质：工程正确性重放；固定 Stage252 top6/r050/pc15/maxpos3，不扫参数。",
        f"- 执行语义：{decision['execution_semantics']}",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## C账户总览",
        "",
        s551._md_table(
            view[
                [
                    "variant",
                    "total_return_pct",
                    "return_vs_stage526_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "satellite_cumulative_pnl",
                    "holding63_p05_improvement_pp",
                    "holding126_p05_improvement_pp",
                    "total_trade_count",
                ]
            ].sort_values("return_vs_stage526_pct", ascending=False)
        ),
        "",
        "## 成本压力",
        "",
        s551._md_table(cost[["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "ulcer_pct", "sharpe"]]),
        "",
        "## 卫星仓 standalone",
        "",
        s551._md_table(satellite_summary),
        "",
        "## 年度选择",
        "",
        s551._md_table(selection_audit, max_rows=80),
        "",
        "## 任意启动3/6个月持有体验",
        "",
        s551._md_table(
            rolling[rolling["holding_days"].isin([63, 126])][
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ]
        ),
        "",
        "## 多窗口",
        "",
        s551._md_table(
            window[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 卫星产品年度贡献",
        "",
        s551._md_table(product_harvest, max_rows=80),
        "",
        "## 入场诊断",
        "",
        s551._md_table(entry_summary),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(s551._json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    s552.REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _retarget_stage552_outputs()
    if not hasattr(s551, "_ORIGINAL_STAGE556_ENTRY_SUMMARY"):
        s551._ORIGINAL_STAGE556_ENTRY_SUMMARY = s551._entry_summary
    s551._entry_summary = _entry_summary_with_raw_snapshots
    if not hasattr(s552, "_ORIGINAL_STAGE556_SLEEVE_OVERRIDES"):
        s552._ORIGINAL_STAGE556_SLEEVE_OVERRIDES = s552._sleeve_overrides
    s552._sleeve_overrides = _sleeve_overrides_with_next_trade_date
    s552._decision = _decision
    s552._plot = _plot
    s552._write_report = _write_report
    s552.main()


if __name__ == "__main__":
    main()

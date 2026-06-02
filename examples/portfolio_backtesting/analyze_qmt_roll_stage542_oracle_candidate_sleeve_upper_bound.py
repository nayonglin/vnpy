from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
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

import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage540_core_preserve_new_sleeve as s540  # noqa: E402


MODEL_TAG = "stage542_oracle_candidate_sleeve_upper_bound_v1"
OUTPUT_PREFIX = "qmt_roll_stage542_oracle_candidate_sleeve_upper_bound"
LINE_ID = "futures_trend_drawdown30_preserve_return"
CONTROL = s540.CONTROL
ACCOUNT_CAPITAL = s540.ACCOUNT_CAPITAL
SLEEVE_CAPITAL = s540.SLEEVE_CAPITAL
STAGE526_RETURN_PCT = s540.STAGE526_RETURN_PCT

FULL_MARKET_UNIVERSE_IN = OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
STAGE541_TAG = "stage541_single_product_opportunity_map_v1"
STAGE541_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
STAGE541_SUMMARY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_summary_{STAGE541_TAG}.csv"
ORACLE_UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oracle6_universe_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


SPECS: tuple[s540.SleeveSpec, ...] = (
    s540.SleeveSpec(
        "core_plus_oracle6_r030_pc15_maxpos3",
        "Stage526 + oracle6 sleeve risk030 pc15 maxpos3",
        0.30,
        0.15,
        3,
        0.30,
        "Stage541材料性产品篮子的hindsight上限验证；不可直接晋级。",
    ),
    s540.SleeveSpec(
        "core_plus_oracle6_r050_pc15_maxpos3",
        "Stage526 + oracle6 sleeve risk050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "Stage541材料性产品篮子的hindsight上限验证；不可直接晋级。",
    ),
    s540.SleeveSpec(
        "core_plus_oracle6_r050_pc10_maxpos4",
        "Stage526 + oracle6 sleeve risk050 pc10 maxpos4",
        0.50,
        0.10,
        4,
        0.30,
        "更分散表达的hindsight上限验证；不可直接晋级。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s540._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s540._md_table(frame, max_rows=max_rows)


def _build_oracle_universe() -> tuple[pd.DataFrame, list[str]]:
    if not STAGE541_SUMMARY_IN.exists():
        raise FileNotFoundError(STAGE541_SUMMARY_IN)
    if not FULL_MARKET_UNIVERSE_IN.exists():
        raise FileNotFoundError(FULL_MARKET_UNIVERSE_IN)
    stage541 = pd.read_csv(STAGE541_SUMMARY_IN, encoding="utf-8-sig")
    selected = stage541[
        pd.to_numeric(stage541["candidate_materiality_pass"], errors="coerce").fillna(0).astype(int).eq(1)
    ].copy()
    selected_products = selected["product_vt_symbol"].astype(str).tolist()
    universe = pd.read_csv(FULL_MARKET_UNIVERSE_IN, encoding="utf-8-sig")
    universe["product_vt_symbol"] = universe["product_vt_symbol"].astype(str)
    oracle = universe[universe["product_vt_symbol"].isin(selected_products)].copy()
    oracle.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    oracle.to_csv(ORACLE_UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    return oracle, selected_products


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, satellite_summary: pd.DataFrame, products: list[str]) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    cost3 = cost[cost["cost_multiplier"].eq(3.0)].set_index("variant")
    r63 = rolling[rolling["holding_days"].eq(63)].set_index("variant")
    r126 = rolling[rolling["holding_days"].eq(126)].set_index("variant")
    control = summary[summary["variant"].eq(CONTROL)].iloc[0].to_dict()
    rows: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        variant = str(item["variant"])
        satellite_row = satellite_summary[satellite_summary["variant"].eq(variant)]
        satellite_pnl = float(satellite_row["sleeve_total_pnl"].iloc[0]) if not satellite_row.empty else 0.0
        h63 = float(r63.loc[variant, "p05_return_pct"]) if variant in r63.index else 0.0
        h126 = float(r126.loc[variant, "p05_return_pct"]) if variant in r126.index else 0.0
        c63 = float(r63.loc[CONTROL, "p05_return_pct"]) if CONTROL in r63.index else 0.0
        c126 = float(r126.loc[CONTROL, "p05_return_pct"]) if CONTROL in r126.index else 0.0
        material_upper_bound = bool(
            variant != CONTROL
            and satellite_pnl >= max(ACCOUNT_CAPITAL * 0.01, SLEEVE_CAPITAL * 0.10)
            and float(item["total_return_pct"]) > float(control["total_return_pct"])
            and float(item["max_dd_pct"]) >= float(control["max_dd_pct"])
            and float(item["max_broker10_margin_to_equity_pct"]) <= 100.0
            and int(item["days_over_100pct"]) == 0
        )
        rows.append(
            {
                **item,
                "satellite_total_pnl": satellite_pnl,
                "two_x_max_dd_pct": float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0,
                "three_x_max_dd_pct": float(cost3.loc[variant, "max_dd_pct"]) if variant in cost3.index else 0.0,
                "holding63_p05_return_pct": h63,
                "holding126_p05_return_pct": h126,
                "holding63_p05_improvement_pp": h63 - c63,
                "holding126_p05_improvement_pp": h126 - c126,
                "material_upper_bound_pass": int(material_upper_bound),
                "upper_bound_score": (
                    (float(item["total_return_pct"]) - float(control["total_return_pct"]))
                    + satellite_pnl / ACCOUNT_CAPITAL * 100.0
                    + (float(item["max_dd_pct"]) - float(control["max_dd_pct"])) * 10.0
                ),
            }
        )
    ranked = sorted(rows, key=lambda x: (x["material_upper_bound_pass"], x["upper_bound_score"]), reverse=True)
    passed = [item for item in ranked if item["material_upper_bound_pass"]]
    return {
        "stage": "Stage542",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "oracle_sleeve_upper_bound_positive_requires_ex_ante_selector" if passed else "oracle_sleeve_upper_bound_not_enough",
        "baseline": CONTROL,
        "oracle_products": products,
        "overfit_boundary": "Products are selected from Stage541 full-sample standalone outcomes. This is an upper-bound diagnostic only, not a tradable promotion candidate.",
        "pass_definition": "Upper bound must add material satellite PnL, improve total return, not worsen max DD, keep broker10<=100 and no over-100 days.",
        "best_variant": ranked[0] if ranked else {},
        "upper_bound_passed": passed,
        "ranked": ranked,
        "next_step": "If positive, do not promote directly; build an ex-ante selector using pre-trade structural/fundamental/market-state features and purged walk-forward.",
    }


def _plot(combo_daily: pd.DataFrame, satellite_daily: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_equity, ax_dd, ax_sat, ax_hold = axes.flatten()
    color_map = {
        CONTROL: "#111827",
        "core_plus_oracle6_r030_pc15_maxpos3": "#2563eb",
        "core_plus_oracle6_r050_pc15_maxpos3": "#dc2626",
        "core_plus_oracle6_r050_pc10_maxpos4": "#059669",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(ordered["date"], ordered["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        dd = s540._drawdown_pct(equity)
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
    ax_equity.set_title("Stage526 + oracle6 sleeve upper bound")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("Drawdown")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(ordered["date"], ordered["net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("Satellite cumulative PnL")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=7)

    h = rolling[rolling["holding_days"].isin([63, 126])].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    pivot = pivot.reindex([CONTROL] + [spec.variant for spec in SPECS])
    pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("63/126 day p05 return")
    ax_hold.grid(axis="x", alpha=0.25)
    fig.suptitle(f"Stage542 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    satellite_summary: pd.DataFrame,
    product_harvest: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)][["variant", "max_dd_pct"]].rename(columns={"max_dd_pct": "max_dd_pct_2x"})
    cost3 = cost[cost["cost_multiplier"].eq(3.0)][["variant", "max_dd_pct"]].rename(columns={"max_dd_pct": "max_dd_pct_3x"})
    view = summary.merge(cost2, on="variant", how="left").merge(cost3, on="variant", how="left")
    keep = [
        "variant",
        "total_return_pct",
        "return_vs_stage526_pct",
        "max_dd_pct",
        "max_dd_pct_2x",
        "max_dd_pct_3x",
        "ulcer_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "satellite_cumulative_pnl",
        "total_trade_count",
    ]
    hold = rolling[rolling["holding_days"].isin([63, 126])][
        ["variant", "holding_days", "p05_return_pct", "median_return_pct", "positive_rate_pct"]
    ]
    product_year = product_harvest.pivot_table(
        index=["variant", "product_vt_symbol"], columns="year", values="satellite_product_net_pnl", aggfunc="sum"
    ).reset_index()
    lines = [
        "# Stage542 Oracle6 卫星仓上限验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：hindsight 上限验证；产品来自 Stage541 全样本单品种机会图，因此不能直接晋级。",
        f"- 产品：`{', '.join(decision['oracle_products'])}`",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 账户总览",
        "",
        _md_table(view[keep]),
        "",
        "## 卫星仓 standalone",
        "",
        _md_table(satellite_summary),
        "",
        "## 3/6个月体验",
        "",
        _md_table(hold),
        "",
        "## 产品年度贡献",
        "",
        _md_table(product_year, max_rows=50),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    oracle, products = _build_oracle_universe()
    if oracle.empty:
        raise RuntimeError("empty oracle universe")
    s540.NEW_UNIVERSE_PATH = ORACLE_UNIVERSE_PATH
    s540.SLEEVE_SPECS = SPECS
    metadata = s540._metadata_for_new_universe()
    identity_map = s540.s519._product_identity_cluster_map(metadata)
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for spec in SPECS:
        print(f"[stage542] running {spec.variant}", flush=True)
        daily, positions, _snapshots = s540._run_sleeve(spec, metadata, identity_map)
        daily_frames.append(daily)
        position_frames.append(positions)
    satellite_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    satellite_margin_daily, satellite_product_margin = s540.s513._position_margin(positions, metadata)
    control_daily = s540._load_control_daily()
    combo_daily = s540._combine_with_core(control_daily, satellite_daily, satellite_margin_daily)
    summary, cost = s540._summary_and_cost(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    satellite_summary = s540._satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    product_harvest = s540._satellite_product_harvest(satellite_product_margin)
    decision = _decision(summary, cost, rolling, satellite_summary, products)
    _plot(combo_daily, satellite_daily, rolling, decision)
    _write_report(summary, cost, rolling, satellite_summary, product_harvest, decision)

    combo_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

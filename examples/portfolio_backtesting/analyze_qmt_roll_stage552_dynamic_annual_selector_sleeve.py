from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
from vnpy.trader.constant import Interval


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage551_annual_persistence_sleeve_replay as s551  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO  # noqa: E402


MODEL_TAG = "stage552_dynamic_annual_selector_sleeve_v1"
OUTPUT_PREFIX = "qmt_roll_stage552_dynamic_annual_selector_sleeve"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = s551.ACCOUNT_CAPITAL
SLEEVE_CAPITAL = s551.SLEEVE_CAPITAL
CONTROL = s551.CONTROL
START_TRADE_DT = datetime(2021, 1, 1)
COST_MULTIPLIERS = s551.COST_MULTIPLIERS
BROKER_MARGIN_MULTIPLIER = s551.BROKER_MARGIN_MULTIPLIER

UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_noncore_commodity_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_eligibility_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
COMBINED_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_daily_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SATELLITE_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_margin_daily_{MODEL_TAG}.csv"
SATELLITE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_product_harvest_{MODEL_TAG}.csv"
SATELLITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_standalone_{MODEL_TAG}.csv"
SELECTION_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_selection_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class DynamicSpec:
    variant: str
    selector_mode: str
    label: str
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
    max_single_trade_capital_usage_ratio: float
    note: str


SPECS: tuple[DynamicSpec, ...] = (
    DynamicSpec(
        "dynamic_prevpos_r050_pc15_maxpos3",
        "prev_year_positive",
        "Stage526 + continuous annual prev-year positive sleeve r050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "连续动态宇宙：上一年真实账本为正的非核心商品允许新开仓；已有持仓自然退出或换月。",
    ),
    DynamicSpec(
        "dynamic_prevtop6_r050_pc15_maxpos3",
        "prev_year_top6",
        "Stage526 + continuous annual prev-year top6 sleeve r050 pc15 maxpos3",
        0.50,
        0.15,
        3,
        0.35,
        "连续动态宇宙：上一年真实账本Top6允许新开仓；已有持仓自然退出或换月。",
    ),
)


def _build_universe_and_eligibility() -> tuple[pd.DataFrame, pd.DataFrame]:
    universe, summary, annual, family = s551._load_inputs()
    noncore = s551._noncore_commodity_products(universe, summary)
    universe_out = universe[universe["product_vt_symbol"].isin(noncore)].copy()
    universe_out.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe_out.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")

    stage_specs = tuple(
        s551.SleeveSpec(
            spec.variant,
            spec.selector_mode,
            spec.label,
            spec.risk_multiplier,
            spec.product_cap_ratio,
            spec.max_concurrent_positions,
            spec.max_single_trade_capital_usage_ratio,
            spec.note,
        )
        for spec in SPECS
    )
    selection = s551._annual_selection_rows(stage_specs, universe, summary, annual, family)
    eligibility_rows: list[dict[str, Any]] = []
    for row in selection.itertuples(index=False):
        products = [item for item in str(row.selected_products).split(",") if item]
        for rank, product in enumerate(products, start=1):
            eligibility_rows.append(
                {
                    "strategy": row.variant,
                    "eval_date": f"{int(row.year)}-01-01",
                    "product_vt_symbol": product,
                    "score": float(len(products) - rank + 1),
                    "score_rank": int(rank),
                    "top_n": int(len(products)),
                    "selector_mode": row.selector_mode,
                    "source_prev_year": int(row.prev_year),
                }
            )
    eligibility = pd.DataFrame(eligibility_rows)
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    selection.to_csv(SELECTION_AUDIT_PATH, index=False, encoding="utf-8-sig")
    return universe_out, selection


def _sleeve_overrides(spec: DynamicSpec, identity_map: str) -> dict[str, Any]:
    return {
        **s513._c3_overrides(START_TRADE_DT),
        **s519._product_cap_overrides(spec.product_cap_ratio, identity_map),
        "product_universe_csv_path": str(UNIVERSE_PATH),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "max_single_trade_capital_usage_ratio": float(spec.max_single_trade_capital_usage_ratio),
        "enable_same_direction_correlation_gate": True,
        "same_direction_correlation_gate_lookback": 20,
        "same_direction_correlation_gate_start": 0.60,
        "same_direction_correlation_gate_full": 0.80,
        "same_direction_correlation_gate_weight_floor": 0.50,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
        "ai_product_pool_strategy": spec.variant,
    }


def _run_dynamic_sleeve(spec: DynamicSpec, metadata: dict[str, Any], identity_map: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    preload_start = max(PRELOAD_START_DT, START_TRADE_DT - timedelta(days=365))
    _, open_map = s506.s501._seed_proxy_maps()
    engine = s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=SLEEVE_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=_sleeve_overrides(spec, identity_map),
    )
    setting.update(
        {
            "capital_base": SLEEVE_CAPITAL,
            "sizing_equity_cap": SLEEVE_CAPITAL,
            "max_capital_usage_ratio": 0.95,
            "enable_incremental_margin_budget_gate": True,
            "incremental_margin_budget_gate_usage_ratio": 0.95,
            "incremental_margin_budget_gate_min_openable_candidates": 1,
            "incremental_margin_budget_gate_protected_selection_rank": 0,
        }
    )
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty sleeve daily: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= s551.START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["sleeve_equity"] = SLEEVE_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["selector_mode"] = spec.selector_mode
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["product_cap_ratio"] = spec.product_cap_ratio
    daily["max_concurrent_positions"] = spec.max_concurrent_positions
    daily["max_single_trade_capital_usage_ratio"] = spec.max_single_trade_capital_usage_ratio
    daily["note"] = spec.note

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["selector_mode"] = spec.selector_mode
    positions["risk_multiplier"] = spec.risk_multiplier
    positions["product_cap_ratio"] = spec.product_cap_ratio
    positions["max_concurrent_positions"] = spec.max_concurrent_positions

    snapshots = pd.DataFrame(getattr(engine.strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
        snapshots["selector_mode"] = spec.selector_mode
        snapshots["risk_multiplier"] = spec.risk_multiplier
    return daily, positions, snapshots


def _combine_with_core(control_daily: pd.DataFrame, satellite_daily: pd.DataFrame, satellite_margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = [control_daily.copy()]
    spec_map = {spec.variant: spec for spec in SPECS}
    for variant, sat in satellite_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        core = control_daily.copy().sort_values("date")
        sat_part = sat[["date", "net_pnl", "slippage", "trade_count", "sleeve_equity"]].rename(
            columns={
                "net_pnl": "satellite_net_pnl",
                "slippage": "satellite_slippage",
                "trade_count": "satellite_trade_count",
            }
        )
        margin_part = satellite_margin_daily[satellite_margin_daily["variant"].eq(variant)][
            ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
        ].rename(
            columns={
                "c3_margin_exact": "satellite_margin_exact",
                "c3_active_contracts": "satellite_active_contracts",
                "c3_active_products": "satellite_active_products",
            }
        )
        merged = core.merge(sat_part, on="date", how="left").merge(margin_part, on="date", how="left")
        for column in [
            "satellite_net_pnl",
            "satellite_slippage",
            "satellite_trade_count",
            "satellite_margin_exact",
            "satellite_active_contracts",
            "satellite_active_products",
        ]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["core_total_net_pnl"] = pd.to_numeric(merged["total_net_pnl"], errors="coerce").fillna(0.0)
        merged["core_total_slippage"] = pd.to_numeric(merged["total_slippage"], errors="coerce").fillna(0.0)
        merged["core_total_margin_exact"] = pd.to_numeric(merged["total_margin_exact"], errors="coerce").fillna(0.0)
        merged["total_net_pnl"] = merged["core_total_net_pnl"] + merged["satellite_net_pnl"]
        merged["total_slippage"] = merged["core_total_slippage"] + merged["satellite_slippage"]
        merged["trade_count"] = pd.to_numeric(merged["trade_count"], errors="coerce").fillna(0.0) + merged[
            "satellite_trade_count"
        ]
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["core_total_margin_exact"] + merged["satellite_margin_exact"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        merged["variant"] = variant
        merged["combo_variant"] = variant
        merged["label"] = spec.label
        merged["selector_mode"] = spec.selector_mode
        merged["risk_multiplier"] = spec.risk_multiplier
        merged["product_cap_ratio"] = spec.product_cap_ratio
        merged["max_concurrent_positions"] = spec.max_concurrent_positions
        merged["note"] = spec.note
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, satellite_summary: pd.DataFrame) -> dict[str, Any]:
    decision = s551._decision(summary, cost, rolling, satellite_summary)
    decision["stage"] = "Stage252"
    decision["model_tag"] = MODEL_TAG
    decision["decision"] = (
        "dynamic_annual_selector_promotion_candidate_found"
        if decision.get("promotion_candidates")
        else "dynamic_annual_selector_not_promotion"
    )
    decision["execution_semantics"] = (
        "连续动态宇宙：非核心商品全集进入引擎，但每年1月1日只允许上一年已知选中产品新开仓；"
        "已有持仓不在年末强平，按原策略自然退出或换月。"
    )
    decision["next_step"] = (
        "若连续动态语义仍通过，再做持仓连续性、2026/lu剔除、成本和真实部署材料性复核；"
        "若失败，则 Stage251 年度重启结果降级为经验。"
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
    fig, axes = plt.subplots(3, 2, figsize=(17, 13))
    ax_equity, ax_dd, ax_sat, ax_hold, ax_product, ax_cost = axes.flatten()
    color_map = {
        CONTROL: "#111827",
        "dynamic_prevpos_r050_pc15_maxpos3": "#dc2626",
        "dynamic_prevtop6_r050_pc15_maxpos3": "#7c3aed",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_equity.plot(ordered["date"], ordered["account_equity"], label=variant, linewidth=0.9, color=color_map.get(variant))
        dd = s551._drawdown_pct(pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"])))
        ax_dd.plot(dd.index, dd.values, label=variant, linewidth=0.8, color=color_map.get(variant))
    ax_equity.set_title("账户权益：连续年度选择卫星")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=7)
    ax_dd.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("账户回撤")
    ax_dd.grid(alpha=0.25)

    for variant, frame in satellite_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        ax_sat.plot(ordered["date"], ordered["net_pnl"].cumsum(), label=variant, linewidth=0.9, color=color_map.get(variant))
    ax_sat.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_sat.set_title("卫星仓累计PnL")
    ax_sat.grid(alpha=0.25)
    ax_sat.legend(fontsize=7)

    h = rolling[rolling["holding_days"].isin([63, 126])].copy()
    pivot = h.pivot(index="variant", columns="holding_days", values="p05_return_pct")
    pivot = pivot.reindex([CONTROL] + [spec.variant for spec in SPECS])
    pivot.plot(kind="barh", ax=ax_hold, color=["#f97316", "#0891b2"])
    ax_hold.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_hold.set_title("任意启动持有3/6个月 p05收益")
    ax_hold.set_xlabel("%")
    ax_hold.grid(axis="x", alpha=0.25)

    top_product = product_harvest.groupby(["variant", "year"], as_index=False)["satellite_product_net_pnl"].sum()
    product_pivot = top_product.pivot(index="year", columns="variant", values="satellite_product_net_pnl").fillna(0.0)
    product_pivot = product_pivot.reindex(columns=[spec.variant for spec in SPECS])
    product_pivot.plot(kind="bar", ax=ax_product, color=[color_map.get(v) for v in product_pivot.columns])
    ax_product.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_product.set_title("卫星仓实际年度PnL")
    ax_product.grid(axis="y", alpha=0.25)

    cost_view = cost.pivot(index="variant", columns="cost_multiplier", values="max_dd_pct")
    cost_view = cost_view.reindex([CONTROL] + [spec.variant for spec in SPECS])
    cost_view.plot(kind="barh", ax=ax_cost, color=["#0f172a", "#ea580c", "#b91c1c"])
    ax_cost.axvline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("1x/2x/3x成本压力最大回撤")
    ax_cost.set_xlabel("%")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage252 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
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
    decision_rank = pd.DataFrame(decision.get("ranked", []))
    view = summary.copy()
    if not decision_rank.empty:
        rank_cols = [
            "variant",
            "holding63_p05_improvement_pp",
            "holding126_p05_improvement_pp",
            "satellite_total_pnl",
            "soft_score",
        ]
        view = view.merge(decision_rank[rank_cols], on="variant", how="left")
    lines = [
        "# Stage252 连续动态年度选品卫星仓审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 阶段性质：Stage251 语义偏差复核。A=`{CONTROL}`；C=Stage526核心不动 + 连续动态年度选品卫星仓。",
        f"- 执行语义：{decision['execution_semantics']}",
        "- 反过拟合边界：只验证 Stage251 最有价值的 `prev_year_positive/top6` + `risk050/pc15/maxpos3`，不再扫 risk/cap/topN。",
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
                    "no_degrade_pass",
                    "materiality_pass",
                    "promotion_pass",
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
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _universe, selection_audit = _build_universe_and_eligibility()
    supported_symbols = load_product_universe_symbols(str(UNIVERSE_PATH))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    identity_map = s519._product_identity_cluster_map(metadata)

    satellite_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for spec in SPECS:
        print(f"[stage552] running {spec.variant}", flush=True)
        daily, positions, snapshots = _run_dynamic_sleeve(spec, metadata, identity_map)
        satellite_frames.append(daily)
        position_frames.append(positions)
        if not snapshots.empty:
            snapshot_frames.append(snapshots)

    satellite_daily = pd.concat(satellite_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    full_metadata = s551._metadata_for_full_universe()
    satellite_margin_daily, satellite_product_margin = s513._position_margin(positions, full_metadata)
    control_daily = s551._load_control_daily()
    combo_daily = _combine_with_core(control_daily, satellite_daily, satellite_margin_daily)

    summary, cost = s551._summary_and_cost(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    window = s551._window_metrics(combo_daily)
    satellite_summary = s551._satellite_standalone_summary(satellite_daily, satellite_margin_daily)
    product_harvest = s551._satellite_product_harvest(satellite_product_margin)
    snapshots = pd.concat(snapshot_frames, ignore_index=True, sort=False) if snapshot_frames else pd.DataFrame()
    entry_summary = s551._entry_summary(snapshots)
    decision = _decision(summary, cost, rolling, satellite_summary)
    summary["no_degrade_pass"] = summary["variant"].map({item["variant"]: item["no_degrade_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["materiality_pass"] = summary["variant"].map({item["variant"]: item["materiality_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["promotion_pass"] = summary["variant"].map({item["variant"]: item["promotion_pass"] for item in decision["ranked"]}).fillna(0).astype(int)
    summary["soft_score"] = summary["variant"].map({item["variant"]: item["soft_score"] for item in decision["ranked"]}).fillna(0.0)

    _plot(cost, rolling, combo_daily, satellite_daily, product_harvest, decision)
    _write_report(summary, cost, rolling, window, satellite_summary, selection_audit, product_harvest, entry_summary, decision)

    combo_daily.to_csv(COMBINED_DAILY_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    satellite_margin_daily.to_csv(SATELLITE_MARGIN_PATH, index=False, encoding="utf-8-sig")
    product_harvest.to_csv(SATELLITE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    satellite_summary.to_csv(SATELLITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(s551._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(s551._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

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
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)
from run_qmt_roll_stage298_stage78_1_risk_cluster_cap import RISK_CLUSTER_MAP  # noqa: E402


MODEL_TAG = "stage517_portfolio_margin_deleverage_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage517_portfolio_margin_deleverage_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
ENTRY_CONTEXTS = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add"

POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
C3_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c3_daily_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_events_{MODEL_TAG}.csv"
PRODUCT_EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_events_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    overrides: dict[str, Any]
    note: str


def _portfolio_margin_deleverage_overrides(
    *,
    start_ratio: float,
    full_ratio: float,
    layer_kinds: str,
    min_pressure: float = 0.50,
) -> dict[str, Any]:
    return {
        "enable_portfolio_margin_deleverage": True,
        "portfolio_margin_deleverage_start_ratio": float(start_ratio),
        "portfolio_margin_deleverage_full_ratio": float(full_ratio),
        "portfolio_margin_deleverage_min_pressure": float(min_pressure),
        "portfolio_margin_deleverage_layer_kinds": layer_kinds,
        "portfolio_margin_deleverage_broker_multiplier": BROKER_MARGIN_MULTIPLIER,
    }


def _risk_cluster_cap_overrides(ratio: float) -> dict[str, Any]:
    return {
        "enable_risk_cluster_margin_cap": True,
        "risk_cluster_margin_cap_ratio": float(ratio),
        "risk_cluster_target_clusters": "",
        "risk_cluster_map": RISK_CLUSTER_MAP,
    }


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        "r060_legacy_nocap_control",
        "risk060 legacy no-cap control",
        0.60,
        {},
        "Stage214/216 risk060 no-cap 对照，不做新增持仓治理。",
    ),
    VariantSpec(
        "r070_legacy_nocap_control",
        "risk070 legacy no-cap control",
        0.70,
        {},
        "Stage214/216 risk070 no-cap 对照，不做新增持仓治理。",
    ),
    VariantSpec(
        "r070_pm_add_80_100",
        "risk070 portfolio-margin add/donchian 80-100",
        0.70,
        _portfolio_margin_deleverage_overrides(
            start_ratio=0.80,
            full_ratio=1.00,
            layer_kinds="add,donchian",
        ),
        "总组合 broker 保证金/权益在 80%-100% 压力区，优先关闭加仓层。",
    ),
    VariantSpec(
        "r070_pm_all_90_110",
        "risk070 portfolio-margin all layers 90-110",
        0.70,
        _portfolio_margin_deleverage_overrides(
            start_ratio=0.90,
            full_ratio=1.10,
            layer_kinds="base,add,donchian",
        ),
        "总组合 broker 保证金/权益在 90%-110% 压力区，允许关闭全部层。",
    ),
    VariantSpec(
        "r080_pm_all_80_100",
        "risk080 portfolio-margin all layers 80-100",
        0.80,
        _portfolio_margin_deleverage_overrides(
            start_ratio=0.80,
            full_ratio=1.00,
            layer_kinds="base,add,donchian",
        ),
        "更高风险预算搭配总保证金主动降杠杆，检验能否保留复利。",
    ),
    VariantSpec(
        "r070_cluster35",
        "risk070 all-cluster cap35",
        0.70,
        _risk_cluster_cap_overrides(0.35),
        "所有风险簇单簇保证金上限 35%，作为风险簇贡献治理对照。",
    ),
    VariantSpec(
        "r070_cluster35_pm_add_80_100",
        "risk070 cluster35 + portfolio-margin add 80-100",
        0.70,
        {
            **_risk_cluster_cap_overrides(0.35),
            **_portfolio_margin_deleverage_overrides(
                start_ratio=0.80,
                full_ratio=1.00,
                layer_kinds="add,donchian",
            ),
        },
        "风险簇 cap 控制结构性拥挤，组合保证金压力只削加仓层。",
    ),
    VariantSpec(
        "r080_cluster35_pm_all_80_100",
        "risk080 cluster35 + portfolio-margin all 80-100",
        0.80,
        {
            **_risk_cluster_cap_overrides(0.35),
            **_portfolio_margin_deleverage_overrides(
                start_ratio=0.80,
                full_ratio=1.00,
                layer_kinds="base,add,donchian",
            ),
        },
        "更高风险预算 + 风险簇 cap + 总保证金主动降杠杆的粗前沿。",
    ),
)

COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


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


def _run_variant(spec: VariantSpec, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    overrides = s513._c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
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
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec.risk_multiplier),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    setting.update(spec.overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.variant}")

    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = C3_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = spec.variant
    daily["combo_variant"] = spec.variant
    daily["label"] = spec.label
    daily["risk_multiplier"] = spec.risk_multiplier
    daily["note"] = spec.note

    strategy = getattr(engine, "strategy", None)
    daily["portfolio_margin_deleverage_count"] = int(getattr(strategy, "portfolio_margin_deleverage_count", 0) or 0)
    daily["risk_cluster_heat_deleverage_count"] = int(getattr(strategy, "risk_cluster_heat_deleverage_count", 0) or 0)
    daily["portfolio_drawdown_deleverage_count"] = int(getattr(strategy, "portfolio_drawdown_deleverage_count", 0) or 0)

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier

    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = spec.variant
        usage["label"] = spec.label
        usage["risk_multiplier"] = spec.risk_multiplier
    return daily, positions, usage


def _combine_daily(c3_daily: pd.DataFrame, margin_daily: pd.DataFrame, xsmom_daily: pd.DataFrame) -> pd.DataFrame:
    x = xsmom_daily[
        ["date", "xsmom_true_daily_pnl", "xsmom_true_slippage_cost", "xsmom_true_margin", "xsmom_true_held_contract_count"]
    ].copy()
    rows: list[pd.DataFrame] = []
    for variant, frame in c3_daily.groupby("variant", sort=False):
        merged = frame.sort_values("date").merge(x, on="date", how="left").merge(
            margin_daily[margin_daily["variant"].eq(variant)][
                ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            ],
            on="date",
            how="left",
        )
        for column in [
            "xsmom_true_daily_pnl",
            "xsmom_true_slippage_cost",
            "xsmom_true_margin",
            "xsmom_true_held_contract_count",
            "c3_margin_exact",
            "c3_active_contracts",
            "c3_active_products",
        ]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["total_net_pnl"] = merged["net_pnl"].astype(float) + merged["xsmom_true_daily_pnl"].astype(float)
        merged["total_slippage"] = merged["slippage"].astype(float) + merged["xsmom_true_slippage_cost"].astype(float)
        merged["account_equity"] = ACCOUNT_CAPITAL + merged["total_net_pnl"].cumsum()
        merged["total_margin_exact"] = merged["c3_margin_exact"] + merged["xsmom_true_margin"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False)


def _summary_and_cost(combo_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    specs = {spec.variant: spec for spec in VARIANTS}
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = specs[variant]
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
                    "portfolio_margin_deleverage_count": int(frame["portfolio_margin_deleverage_count"].max()),
                    "risk_cluster_heat_deleverage_count": int(frame["risk_cluster_heat_deleverage_count"].max()),
                    "note": spec.note,
                }
            )
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame) -> dict[str, Any]:
    cost_2x = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    ranked: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        variant = str(item["variant"])
        two_x = cost_2x.loc[variant] if variant in cost_2x.index else None
        dd2_pass = int(float(two_x["max_dd_pct"]) >= -40.0) if two_x is not None else 0
        hard_pass = int(
            int(item["dd40_pass"]) == 1
            and int(item["broker10_100_pass"]) == 1
            and dd2_pass == 1
        )
        strong_pass = int(hard_pass and int(item["broker10_90_pass"]) == 1 and float(item["return_retention_vs_stage079_pct"]) >= 50.0)
        score = (
            float(item["return_retention_vs_stage079_pct"])
            - max(0.0, float(item["max_broker10_margin_to_equity_pct"]) - 100.0) * 2.0
            + max(-40.0, float(item["max_dd_pct"]))
        )
        ranked.append(
            {
                "variant": variant,
                "label": str(item["label"]),
                "hard_pass": hard_pass,
                "strong_pass": strong_pass,
                "dd2_pass": dd2_pass,
                "score": score,
                "return_retention_vs_stage079_pct": float(item["return_retention_vs_stage079_pct"]),
                "max_dd_pct": float(item["max_dd_pct"]),
                "max_broker10_margin_to_equity_pct": float(item["max_broker10_margin_to_equity_pct"]),
                "days_over_100pct": int(item["days_over_100pct"]),
                "days_over_90pct": int(item["days_over_90pct"]),
                "portfolio_margin_deleverage_count": int(item["portfolio_margin_deleverage_count"]),
            }
        )
    ranked = sorted(ranked, key=lambda item: (item["strong_pass"], item["hard_pass"], item["score"]), reverse=True)
    best = ranked[0] if ranked else {}
    if best.get("strong_pass"):
        label = "portfolio_margin_deleverage_strong_candidate"
    elif best.get("hard_pass"):
        label = "portfolio_margin_deleverage_hard_pass_but_retention_or_90cap_weak"
    else:
        label = "portfolio_margin_deleverage_not_ready"
    holding_126 = rolling[rolling["holding_days"].eq(126)].copy()
    best_126 = (
        holding_126.sort_values(["p10_return_pct", "positive_rate_pct"], ascending=[False, False]).head(1).to_dict(orient="records")
        if not holding_126.empty
        else []
    )
    return {
        "stage": "Stage217",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "best_variant": best,
        "best_126d_holding_experience": best_126[0] if best_126 else {},
        "ranked_variants": ranked,
        "next_step": (
            "Promote only if exact margin and DD40 pass without destroying return. "
            "If all variants fail, stop margin-deleverage threshold sweeps and pivot to independent low-margin alpha."
        ),
    }


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    selected = ["r060_legacy_nocap_control", "r070_legacy_nocap_control"]
    for item in decision.get("ranked_variants", []):
        variant = item["variant"]
        if variant not in selected:
            selected.append(variant)
        if len(selected) >= 6:
            break

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax_nav, ax_dd, ax_margin, ax_scatter = axes.ravel()
    colors = plt.cm.tab10(np.linspace(0, 1, max(10, len(selected))))
    color_map = {variant: colors[idx] for idx, variant in enumerate(selected)}

    for variant, frame in combo_daily[combo_daily["variant"].isin(selected)].groupby("variant", sort=False):
        frame = frame.sort_values("date")
        x = pd.to_datetime(frame["date"])
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=x)
        label = str(frame["label"].iloc[0])
        ax_nav.plot(x, equity / ACCOUNT_CAPITAL, label=label, linewidth=1.05, color=color_map.get(variant))
        ax_dd.plot(x, s516._drawdown_pct(equity), label=label, linewidth=0.95, color=color_map.get(variant))
        ax_margin.plot(x, frame["broker10_margin_to_equity_pct"].astype(float), label=label, linewidth=0.95, color=color_map.get(variant))

    ax_nav.set_title("NAV: next-real C3 variants + fixed true xsmom")
    ax_nav.set_ylabel("NAV")
    ax_nav.grid(True, alpha=0.22)
    ax_nav.legend(fontsize=7)
    ax_dd.set_title("Underwater drawdown")
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_dd.grid(True, alpha=0.22)
    ax_margin.set_title("Broker10 exact margin / equity")
    ax_margin.set_ylabel("Margin / equity %")
    ax_margin.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_margin.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_margin.grid(True, alpha=0.22)

    plot_summary = summary[summary["variant"].isin(selected)].copy()
    ax_scatter.scatter(
        plot_summary["return_retention_vs_stage079_pct"],
        plot_summary["max_broker10_margin_to_equity_pct"],
        s=70,
        c=[color_map.get(v, "#333333") for v in plot_summary["variant"]],
    )
    for row in plot_summary.itertuples(index=False):
        ax_scatter.annotate(str(row.variant).replace("_", "\n"), (row.return_retention_vs_stage079_pct, row.max_broker10_margin_to_equity_pct), fontsize=7)
    ax_scatter.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_scatter.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_scatter.axvline(50.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_scatter.set_title("Return retention vs exact margin")
    ax_scatter.set_xlabel("Retention vs Stage079 deployed return %")
    ax_scatter.set_ylabel("Max broker10 margin / equity %")
    ax_scatter.grid(True, alpha=0.22)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    windows: pd.DataFrame,
    rolling: pd.DataFrame,
    events: pd.DataFrame,
    product_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    full = summary.sort_values(["broker10_100_pass", "return_retention_vs_stage079_pct"], ascending=[False, False])
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    roll_view = rolling.sort_values(["holding_days", "p10_return_pct"], ascending=[True, False])
    report = [
        "# Stage217 组合保证金主动降杠杆粗前沿",
        "",
        f"- 生成时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：A/C 结构实验；固定 Stage079/C3 信号与 Stage103 xsmom true leg，只测试持仓期保证金治理。",
        "- A/B触发判断：触发 A/C。该能力属于资金/保证金治理层，若通过可能成为部署层候选。",
        "- 运行前过拟合判断：否。规则只使用当时可见的估算保证金、权益和通用风险簇，不按坏品种/坏日期过滤。",
        "- 运行前继续价值判断：是。Stage216 已反证静态 cap，下一步必须验证主动持仓治理。",
        "",
        "## 外部调研判断",
        "",
        "- 交易所保证金、强平和风控规则说明，实盘候选必须把保证金作为硬约束；不能用事后曲线解释真实可成交性。",
        "- vn.py/VeighNa 这类事件驱动系统更适合在策略/风控层做下单与持仓治理，本阶段把机制放进策略默认关闭钩子，回测后再用 exact position margin 验收。",
        "",
        "## 预声明通过标准",
        "",
        "- 正常成本：最大回撤 `>= -40%`。",
        "- 正常成本：exact broker10 保证金/权益全程 `<= 100%`；强通过要求 `<= 90%`。",
        "- 2x 成本压力：最大回撤 `>= -40%`。",
        "- 收益保留：硬通过后再看相对 Stage079 部署收益保留是否接近或超过 `50%`；否则只算工程可行但资本效率弱。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最优综合候选：`{decision.get('best_variant', {}).get('variant', '')}`。",
        f"- 最优候选收益保留/最大回撤/最大 broker10 保证金："
        f"`{decision.get('best_variant', {}).get('return_retention_vs_stage079_pct', 0.0):.4f}% / "
        f"{decision.get('best_variant', {}).get('max_dd_pct', 0.0):.4f}% / "
        f"{decision.get('best_variant', {}).get('max_broker10_margin_to_equity_pct', 0.0):.4f}%`。",
        "",
        "## 全周期 1x 成本 exact margin",
        "",
        s516._md_table(
            full[
                [
                    "variant",
                    "label",
                    "risk_multiplier",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "portfolio_margin_deleverage_count",
                    "dd40_pass",
                    "broker10_100_pass",
                    "broker10_90_pass",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        s516._md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "dd40_pass",
                    "broker10_100_pass",
                ]
            ],
            max_rows=48,
        ),
        "",
        "## 多起点/分段",
        "",
        s516._md_table(
            windows[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ].sort_values(["variant", "window_name"]),
            max_rows=90,
        ),
        "",
        "## 任意时点启动后的持有体验",
        "",
        s516._md_table(
            roll_view[
                [
                    "variant",
                    "holding_days",
                    "min_return_pct",
                    "p05_return_pct",
                    "p10_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=140,
        ),
        "",
        "## 关键事件日",
        "",
        s516._md_table(
            events.sort_values(["variant", "broker10_margin_to_equity_pct"], ascending=[True, False])[
                [
                    "variant",
                    "date",
                    "account_equity",
                    "drawdown_pct",
                    "broker10_margin_to_equity_pct",
                    "c3_margin_exact",
                    "xsmom_true_margin",
                    "c3_active_products",
                    "xsmom_true_held_contract_count",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 关键事件日 C3 产品保证金",
        "",
        s516._md_table(
            product_events[
                [
                    "variant",
                    "event_date",
                    "product_vt_symbol",
                    "c3_margin_exact",
                    "active_contracts",
                    "holding_pnl",
                    "trading_pnl",
                    "net_pnl",
                ]
            ].sort_values(["variant", "event_date", "c3_margin_exact"], ascending=[True, True, False]),
            max_rows=120,
        )
        if not product_events.empty
        else "无数据。",
        "",
        "## 图表视觉复盘",
        "",
        "- 图表用于观察主动降杠杆是否真的把保证金线压到 100% 以下，同时 NAV 不像 Stage216 cap 版本那样塌缩。",
        "- 若曲线只在压力区降低少量峰值，但散点仍高于 100%，说明当前触发慢或削减层级不够。",
        "- 若保证金合格但 NAV 远低于 no-cap，则说明它和静态 cap 一样，本质是砍复利。",
        "",
        "## 结论",
        "",
        "- 本阶段不按单一最优收益挑版本，只按 exact margin、DD40、2x成本和收益保留排序。",
        "- 如果没有 hard pass，不继续围绕 `0.80/0.90/1.00/1.10` 阈值小数救援；后续应转向低保证金独立收益源或更底层的真实保证金率/逐笔风控仿真。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：以最终决策为准；粗档结构验证本身不是过拟合，继续救阈值小数会变成过拟合。",
        "- 运行后继续价值判断：以最终决策为准；若主动降杠杆仍无法过 exact margin，则该方向价值下降。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    for spec in VARIANTS:
        print(f"[stage517] running {spec.variant}", flush=True)
        daily, positions, usage = _run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
        if not usage.empty:
            usage_frames.append(usage)

    c3_daily = pd.concat(daily_frames, ignore_index=True)
    positions = pd.concat(position_frames, ignore_index=True)
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = _combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily)
    windows = s516._window_metrics(combo_daily)
    rolling = s516._rolling_holding(combo_daily)
    events, product_events = s516._event_days(combo_daily, product_margin)
    decision = _decision(summary, cost, rolling)
    _plot(combo_daily, summary, decision)
    _write_report(summary, cost, windows, rolling, events, product_events, decision)

    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    c3_daily.to_csv(C3_DAILY_PATH, index=False, encoding="utf-8-sig")
    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_events.to_csv(PRODUCT_EVENT_PATH, index=False, encoding="utf-8-sig")
    usage_all = pd.concat(usage_frames, ignore_index=True) if usage_frames else pd.DataFrame()
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

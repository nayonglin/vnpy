from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval

import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage577_stage526_failure_memory_micro_sizing_replay_v1"
OUTPUT_PREFIX = "qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
BASELINE_STAGE079_RETURN_PCT = 4_947.260162601626
BROKER_MARGIN_MULTIPLIER = float(s513.s403.BROKER10_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidate_snapshots_{MODEL_TAG}.csv"
MICRO_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_micro_sizing_events_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_trigger_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
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


REFERENCE_LINKS = [
    "Clare et al. trend following / stop-loss caveat: https://link.springer.com/article/10.1057/jam.2013.11",
    "pysystemtrade position sizing architecture: https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization",
    "Concretum trend-following position sizing comparison: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/",
    "Davidsson position sizing / trend following risk management: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2248261",
]


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


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


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
    stage526 = {**pc25, "max_concurrent_positions": 4}
    micro = {
        **stage526,
        "enable_failure_memory_micro_sizing": True,
        "failure_memory_micro_sizing_lookback_days": 252,
        "failure_memory_micro_sizing_min_consecutive_failures": 2,
        "failure_memory_micro_sizing_multiplier": 1.10,
        "failure_memory_micro_sizing_entry_contexts": "flat_entry",
    }
    return (
        VariantSpec(
            "stage526_control",
            "Stage526 control",
            0.80,
            stage526,
            "A：Stage526 r080_pc25_maxpos4，不启用失败记忆。",
        ),
        VariantSpec(
            "stage526_failure_memory_micro_sizing",
            "Stage526 + failure-memory micro sizing",
            0.80,
            micro,
            "C：同品种同方向连续失败>=2后，仅flat_entry风险乘数乘以1.10。",
        ),
    )


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
    daily["failure_memory_micro_sizing_count"] = int(
        getattr(strategy, "failure_memory_micro_sizing_count", 0) or 0
    )

    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.variant}")
    positions["variant"] = spec.variant
    positions["combo_variant"] = spec.variant
    positions["label"] = spec.label
    positions["risk_multiplier"] = spec.risk_multiplier

    snapshots = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []))
    if not snapshots.empty:
        snapshots["variant"] = spec.variant
        snapshots["label"] = spec.label
        snapshots["risk_multiplier"] = spec.risk_multiplier
    return daily, positions, snapshots


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
                    "failure_memory_micro_sizing_count": int(
                        frame["failure_memory_micro_sizing_count"].max()
                        if "failure_memory_micro_sizing_count" in frame.columns
                        else 0
                    ),
                    "note": spec.note,
                }
            )
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _micro_events(snapshots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if snapshots.empty:
        return pd.DataFrame(), pd.DataFrame()
    frame = snapshots.copy()
    for column in [
        "failure_memory_micro_sizing_applied",
        "failure_memory_micro_sizing_consecutive_failures",
        "selected_volume",
        "risk_multiplier",
        "failure_memory_micro_sizing_base_multiplier",
        "failure_memory_micro_sizing_effective_multiplier",
    ]:
        frame[column] = _num(frame, column)
    events = frame[
        frame["variant"].eq("stage526_failure_memory_micro_sizing")
        & frame["candidate_status"].eq("opened")
        & frame["failure_memory_micro_sizing_applied"].eq(1)
    ].copy()
    if events.empty:
        return events, pd.DataFrame()
    product_summary = (
        events.groupby(["product_vt_symbol", "direction"], as_index=False)
        .agg(
            trigger_count=("candidate_index", "count"),
            avg_consecutive_failures=("failure_memory_micro_sizing_consecutive_failures", "mean"),
            avg_selected_volume=("selected_volume", "mean"),
            avg_base_multiplier=("failure_memory_micro_sizing_base_multiplier", "mean"),
            avg_effective_multiplier=("failure_memory_micro_sizing_effective_multiplier", "mean"),
        )
        .sort_values(["trigger_count", "product_vt_symbol"], ascending=[False, True])
    )
    return events, product_summary


def _metric(summary: pd.DataFrame, variant: str, column: str) -> float:
    rows = summary[summary["variant"].eq(variant)]
    if rows.empty:
        return float("nan")
    return float(rows.iloc[0][column])


def _cost_metric(cost: pd.DataFrame, variant: str, multiplier: float, column: str) -> float:
    rows = cost[(cost["variant"].eq(variant)) & (cost["cost_multiplier"].eq(multiplier))]
    if rows.empty:
        return float("nan")
    return float(rows.iloc[0][column])


def _rolling_metric(rolling: pd.DataFrame, variant: str, holding_days: int, column: str) -> float:
    rows = rolling[(rolling["variant"].eq(variant)) & (rolling["holding_days"].eq(holding_days))]
    if rows.empty:
        return float("nan")
    return float(rows.iloc[0][column])


def _build_gates(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, micro_events: pd.DataFrame) -> pd.DataFrame:
    a = "stage526_control"
    c = "stage526_failure_memory_micro_sizing"
    rows = [
        {
            "gate": "total_return_not_degrade",
            "control": _metric(summary, a, "total_return_pct"),
            "candidate": _metric(summary, c, "total_return_pct"),
            "threshold": "C >= A",
            "passed": int(_metric(summary, c, "total_return_pct") >= _metric(summary, a, "total_return_pct")),
        },
        {
            "gate": "max_dd_not_degrade",
            "control": _metric(summary, a, "max_dd_pct"),
            "candidate": _metric(summary, c, "max_dd_pct"),
            "threshold": "C >= A",
            "passed": int(_metric(summary, c, "max_dd_pct") >= _metric(summary, a, "max_dd_pct")),
        },
        {
            "gate": "ulcer_not_degrade",
            "control": _metric(summary, a, "ulcer_pct"),
            "candidate": _metric(summary, c, "ulcer_pct"),
            "threshold": "C <= A",
            "passed": int(_metric(summary, c, "ulcer_pct") <= _metric(summary, a, "ulcer_pct")),
        },
        {
            "gate": "sharpe_not_degrade",
            "control": _metric(summary, a, "sharpe"),
            "candidate": _metric(summary, c, "sharpe"),
            "threshold": "C >= A",
            "passed": int(_metric(summary, c, "sharpe") >= _metric(summary, a, "sharpe")),
        },
        {
            "gate": "broker10_not_degrade",
            "control": _metric(summary, a, "max_broker10_margin_to_equity_pct"),
            "candidate": _metric(summary, c, "max_broker10_margin_to_equity_pct"),
            "threshold": "C <= A",
            "passed": int(
                _metric(summary, c, "max_broker10_margin_to_equity_pct")
                <= _metric(summary, a, "max_broker10_margin_to_equity_pct")
            ),
        },
        {
            "gate": "cost_2x_dd_not_degrade",
            "control": _cost_metric(cost, a, 2.0, "max_dd_pct"),
            "candidate": _cost_metric(cost, c, 2.0, "max_dd_pct"),
            "threshold": "C >= A",
            "passed": int(_cost_metric(cost, c, 2.0, "max_dd_pct") >= _cost_metric(cost, a, 2.0, "max_dd_pct")),
        },
        {
            "gate": "cost_3x_dd_not_degrade",
            "control": _cost_metric(cost, a, 3.0, "max_dd_pct"),
            "candidate": _cost_metric(cost, c, 3.0, "max_dd_pct"),
            "threshold": "C >= A",
            "passed": int(_cost_metric(cost, c, 3.0, "max_dd_pct") >= _cost_metric(cost, a, 3.0, "max_dd_pct")),
        },
        {
            "gate": "hold63_left_tail_not_degrade",
            "control": _rolling_metric(rolling, a, 63, "p05_return_pct"),
            "candidate": _rolling_metric(rolling, c, 63, "p05_return_pct"),
            "threshold": "C >= A",
            "passed": int(_rolling_metric(rolling, c, 63, "p05_return_pct") >= _rolling_metric(rolling, a, 63, "p05_return_pct")),
        },
        {
            "gate": "hold126_left_tail_not_degrade",
            "control": _rolling_metric(rolling, a, 126, "p05_return_pct"),
            "candidate": _rolling_metric(rolling, c, 126, "p05_return_pct"),
            "threshold": "C >= A",
            "passed": int(_rolling_metric(rolling, c, 126, "p05_return_pct") >= _rolling_metric(rolling, a, 126, "p05_return_pct")),
        },
        {
            "gate": "micro_trigger_sample_exists",
            "control": 0.0,
            "candidate": float(len(micro_events)),
            "threshold": ">=5 opened triggers",
            "passed": int(len(micro_events) >= 5),
        },
    ]
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, micro_events: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    pass_count = int(gates["passed"].sum()) if not gates.empty else 0
    gate_count = int(len(gates))
    c = "stage526_failure_memory_micro_sizing"
    a = "stage526_control"
    no_degrade = bool(pass_count == gate_count)
    improvement = (
        _metric(summary, c, "total_return_pct") > _metric(summary, a, "total_return_pct")
        or _rolling_metric(rolling, c, 63, "p05_return_pct") > _rolling_metric(rolling, a, 63, "p05_return_pct")
        or _rolling_metric(rolling, c, 126, "p05_return_pct") > _rolling_metric(rolling, a, 126, "p05_return_pct")
    )
    if no_degrade and improvement:
        decision = "failure_memory_micro_sizing_candidate_next_validation"
    elif len(micro_events) == 0:
        decision = "failure_memory_micro_sizing_no_effect"
    else:
        decision = "failure_memory_micro_sizing_no_promotion"
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "arms": {
            "A": "stage526_control",
            "C": "stage526_control + consecutive_loss>=2 same product/direction flat-entry risk multiplier * 1.10",
        },
        "predeclared_rule": {
            "lookback_days": 252,
            "min_consecutive_failures": 2,
            "multiplier": 1.10,
            "entry_contexts": "flat_entry",
            "threshold_sweep": False,
            "product_list": "none",
        },
        "summary": {
            "gate_pass_count": pass_count,
            "gate_count": gate_count,
            "micro_opened_trigger_count": int(len(micro_events)),
            "control_total_return_pct": _metric(summary, a, "total_return_pct"),
            "candidate_total_return_pct": _metric(summary, c, "total_return_pct"),
            "control_max_dd_pct": _metric(summary, a, "max_dd_pct"),
            "candidate_max_dd_pct": _metric(summary, c, "max_dd_pct"),
            "control_ulcer_pct": _metric(summary, a, "ulcer_pct"),
            "candidate_ulcer_pct": _metric(summary, c, "ulcer_pct"),
            "control_broker10_max_pct": _metric(summary, a, "max_broker10_margin_to_equity_pct"),
            "candidate_broker10_max_pct": _metric(summary, c, "max_broker10_margin_to_equity_pct"),
            "control_3x_max_dd_pct": _cost_metric(cost, a, 3.0, "max_dd_pct"),
            "candidate_3x_max_dd_pct": _cost_metric(cost, c, 3.0, "max_dd_pct"),
            "control_hold63_p05_return_pct": _rolling_metric(rolling, a, 63, "p05_return_pct"),
            "candidate_hold63_p05_return_pct": _rolling_metric(rolling, c, 63, "p05_return_pct"),
            "control_hold126_p05_return_pct": _rolling_metric(rolling, a, 126, "p05_return_pct"),
            "candidate_hold126_p05_return_pct": _rolling_metric(rolling, c, 126, "p05_return_pct"),
        },
        "overfit_reflection": "Not overfit if treated as a single predeclared paper probe: no product list, no threshold sweep, no weak-window patch. Promotion would become overfit if a failed result is rescued by changing >=2, 252d, or 1.10.",
        "continue_value_reflection": "Worth one real-engine replay because Stage262 showed diagnostic edge and this test measures recursive state, margin, cost, and path impact. If gates fail, this sub-route should stop.",
        "references": REFERENCE_LINKS,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "rolling": str(ROLLING_PATH),
            "window": str(WINDOW_PATH),
            "snapshots": str(SNAPSHOT_PATH),
            "micro_events": str(MICRO_EVENTS_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, product_summary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_equity, ax_dd, ax_cost, ax_events = axes.flatten()
    colors = {
        "stage526_control": "#2563eb",
        "stage526_failure_memory_micro_sizing": "#dc2626",
    }
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        equity = ordered["account_equity"].astype(float)
        dd = (equity / equity.cummax() - 1.0) * 100.0
        ax_equity.plot(ordered["date"], equity, label=variant, color=colors.get(variant), linewidth=1.0)
        ax_dd.plot(ordered["date"], dd, label=variant, color=colors.get(variant), linewidth=0.95)
    ax_equity.set_title("A/C account equity")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=8)
    ax_dd.axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    ax_dd.set_title("Underwater path")
    ax_dd.set_ylabel("%")
    ax_dd.grid(alpha=0.25)

    cost_view = cost[cost["cost_multiplier"].isin([1.0, 2.0, 3.0])].copy()
    cost_pivot = cost_view.pivot_table(index="cost_multiplier", columns="variant", values="max_dd_pct", aggfunc="first")
    x = np.arange(len(cost_pivot.index))
    width = 0.36
    ax_cost.bar(x - width / 2, cost_pivot["stage526_control"], width=width, label="A", color="#2563eb")
    ax_cost.bar(x + width / 2, cost_pivot["stage526_failure_memory_micro_sizing"], width=width, label="C", color="#dc2626")
    ax_cost.axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_xticks(x)
    ax_cost.set_xticklabels([f"{v:g}x" for v in cost_pivot.index])
    ax_cost.set_title("Cost-stress max DD")
    ax_cost.set_ylabel("%")
    ax_cost.grid(axis="y", alpha=0.25)
    ax_cost.legend(fontsize=8)

    if product_summary.empty:
        ax_events.text(0.5, 0.5, "No opened micro-sizing events", ha="center", va="center")
        ax_events.set_axis_off()
    else:
        top = product_summary.head(10).copy()
        top["label"] = top["product_vt_symbol"].astype(str) + " " + top["direction"].astype(str)
        ax_events.barh(top["label"], top["trigger_count"], color="#f97316")
        ax_events.invert_yaxis()
        ax_events.set_title("Opened micro-sizing triggers by product/direction")
        ax_events.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    window: pd.DataFrame,
    micro_events: pd.DataFrame,
    product_summary: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_view = summary[
        [
            "variant",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "ulcer_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "failure_memory_micro_sizing_count",
        ]
    ].copy()
    cost_view = cost[cost["cost_multiplier"].isin([1.0, 2.0, 3.0])][
        ["variant", "cost_multiplier", "total_return_pct", "max_dd_pct", "ulcer_pct", "sharpe"]
    ].copy()
    rolling_view = rolling[rolling["holding_days"].isin([63, 126])][
        ["variant", "holding_days", "p05_return_pct", "p10_return_pct", "median_return_pct", "loss_rate_pct", "min_window_dd_pct"]
    ].copy()
    lines = [
        "# Stage577 Stage526 failure-memory micro-sizing真实引擎回放",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`",
        "- A：Stage526 `r080_pc25_maxpos4`。",
        "- C：A + 同品种同方向连续失败 `>=2` 后，仅 `flat_entry` 风险乘数乘以 `1.10`。",
        "- 阈值搜索：无。产品名单：无。弱窗口补丁：无。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟踪资料普遍支持把 sizing 当作组合风险治理核心，但也警告 stop-loss/频繁交易可能伤害趋势右尾。",
        "- 本地判断：如果失败记忆有效，它更应表现为轻量 sizing，而不是信号过滤；但亏损后加风险天然有追损风险，所以必须用真实引擎和不劣化闸门。",
        "- 参考链接：",
        *[f"  - {link}" for link in REFERENCE_LINKS],
        "",
        "## 全周期",
        "",
        _md_table(summary_view),
        "",
        "## 成本压力",
        "",
        _md_table(cost_view),
        "",
        "## 3个月/6个月任意启动体验",
        "",
        _md_table(rolling_view),
        "",
        "## 晋级闸门",
        "",
        _md_table(gates),
        "",
        "## Micro-sizing触发",
        "",
        f"- opened trigger count：`{len(micro_events)}`",
        "",
        _md_table(product_summary, max_rows=20),
        "",
        "## 视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 左上看权益曲线是否真实分叉；如果只是末端微小差异，说明规则材料性不足。",
        "- 左下看成本压力，尤其 `3x` 是否进一步穿过 DD40；这是 Stage526 现有未关账项。",
        "- 右下看触发是否集中在少数产品/方向；若过度集中，不能解释为通用失败记忆机制。",
        "",
        "## 决策 JSON",
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
    snapshot_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"[stage577] running {spec.variant}", flush=True)
        daily, positions, snapshots = _run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
        snapshot_frames.append(snapshots)

    c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    snapshots = pd.concat([frame for frame in snapshot_frames if not frame.empty], ignore_index=True, sort=False)
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = s517._combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily, specs)
    rolling = s516._rolling_holding(combo_daily)
    window = s516._window_metrics(combo_daily)
    micro_events, product_summary = _micro_events(snapshots)
    gates = _build_gates(summary, cost, rolling, micro_events)
    decision = _decision(summary, cost, rolling, micro_events, gates)
    _plot(combo_daily, summary, cost, rolling, product_summary)
    _write_report(summary, cost, rolling, window, micro_events, product_summary, gates, decision)

    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    snapshots.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    micro_events.to_csv(MICRO_EVENTS_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

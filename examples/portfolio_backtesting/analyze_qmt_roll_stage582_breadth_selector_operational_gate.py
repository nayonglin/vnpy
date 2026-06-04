from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage582_breadth_selector_operational_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage582_breadth_selector_operational_gate"

STAGE574_TAG = "stage574_low_single_risk_breadth_selector_boundary_v1"
STAGE574_PREFIX = "qmt_roll_stage574_low_single_risk_breadth_selector_boundary"
STAGE571_TAG = "stage571_external_selector_source_priority_audit_v1"
STAGE571_PREFIX = "qmt_roll_stage571_external_selector_source_priority_audit"
STAGE561_TAG = "stage561_selector_predictive_audit_protocol_v1"
STAGE561_PREFIX = "qmt_roll_stage561_selector_predictive_audit_protocol"

STAGE574_CANDIDATE = OUTPUT_DIR / f"{STAGE574_PREFIX}_candidate_map_{STAGE574_TAG}.csv"
STAGE574_PAIRWISE = OUTPUT_DIR / f"{STAGE574_PREFIX}_pairwise_corr_{STAGE574_TAG}.csv"
STAGE574_RISK_SHELL = OUTPUT_DIR / f"{STAGE574_PREFIX}_risk_shell_boundary_{STAGE574_TAG}.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / f"{STAGE571_PREFIX}_source_priority_{STAGE571_TAG}.csv"
STAGE561_GATES = OUTPUT_DIR / f"{STAGE561_PREFIX}_gates_{STAGE561_TAG}.csv"
MASTER_LEDGER = LEDGER_DIR / "external_state_forward_ledger.csv"
SENTIMENT_LEDGER = LEDGER_DIR / "sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv"

WATCHLIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watchlist_{MODEL_TAG}.csv"
ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_matrix_{MODEL_TAG}.csv"
FAMILY_BUDGET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_budget_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_MIN_PRODUCTS = 5
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_ACTIVE_ROUTES_PER_PRODUCT = 2
MAX_AVG_PAIRWISE_ABS_CORR = 0.20
MAX_PAIRWISE_ABS_CORR = 0.50
MAX_FAMILY_BUDGET_PCT = 20.0
MAX_PRODUCT_RISK_UNIT = 0.20


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _stage561_progress() -> dict[str, Any]:
    gates = _read_csv(STAGE561_GATES)
    result: dict[str, Any] = {"passed": int(gates["passed"].astype(bool).sum()), "total": int(len(gates))}
    for _, row in gates.iterrows():
        gate = str(row["gate"])
        result[f"{gate}_passed"] = bool(row["passed"])
        result[f"{gate}_current"] = row.get("current", "")
        result[f"{gate}_required"] = row.get("required", "")
    return result


def _parse_progress_int(value: Any, default: int = 0) -> int:
    text = str(value)
    try:
        return int(float(text.split("/")[0].strip()))
    except (TypeError, ValueError):
        return default


def _latest_forward_route_matrix(products: list[str]) -> pd.DataFrame:
    ledgers: list[pd.DataFrame] = []
    if MASTER_LEDGER.exists():
        master = _read_csv(MASTER_LEDGER)
        ledgers.append(master)
    if SENTIMENT_LEDGER.exists():
        sentiment = _read_csv(SENTIMENT_LEDGER)
        ledgers.append(sentiment)
    if not ledgers:
        return pd.DataFrame(columns=["product_vt_symbol"])

    ledger = pd.concat(ledgers, ignore_index=True, sort=False)
    ledger = ledger[ledger["product_vt_symbol"].astype(str).isin(products)].copy()
    if ledger.empty:
        return pd.DataFrame({"product_vt_symbol": products})

    ledger["received_at_local_ts"] = pd.to_datetime(ledger.get("received_at_local"), errors="coerce")
    ledger["usable_for_forward_monitor"] = pd.to_numeric(
        ledger.get("usable_for_forward_monitor", pd.Series(0, index=ledger.index)),
        errors="coerce",
    ).fillna(0).astype(int)
    ledger["status"] = ledger.get("status", "").fillna("").astype(str)
    ledger["route"] = ledger.get("route", "").fillna("").astype(str)
    ledger["route_group"] = np.where(
        ledger["route"].isin(["manual_event", "sentiment_news"]),
        "sentiment_news_manual_event",
        ledger["route"],
    )

    rows: list[dict[str, Any]] = []
    for product in products:
        item = {"product_vt_symbol": product}
        product_rows = ledger[ledger["product_vt_symbol"].astype(str).eq(product)].copy()
        route_ready_count = 0
        ready_routes: list[str] = []
        latest_dates: list[str] = []
        for route in ["basis", "inventory", "sentiment_news_manual_event"]:
            route_rows = product_rows[product_rows["route_group"].eq(route)].copy()
            latest = route_rows.sort_values("received_at_local_ts").tail(1)
            ready = (
                not latest.empty
                and str(latest.iloc[0].get("status", "")) == "ok"
                and int(latest.iloc[0].get("usable_for_forward_monitor", 0)) == 1
            )
            item[f"{route}_ready"] = int(ready)
            item[f"{route}_latest_status"] = str(latest.iloc[0].get("status", "")) if not latest.empty else ""
            item[f"{route}_latest_received_at"] = (
                latest.iloc[0]["received_at_local_ts"].isoformat()
                if not latest.empty and pd.notna(latest.iloc[0]["received_at_local_ts"])
                else ""
            )
            if ready:
                route_ready_count += 1
                ready_routes.append(route)
                latest_dates.append(item[f"{route}_latest_received_at"])
        item["route_ready_count"] = route_ready_count
        item["ready_routes"] = ",".join(ready_routes)
        item["latest_received_at_max"] = max(latest_dates) if latest_dates else ""
        rows.append(item)
    return pd.DataFrame(rows)


def build_watchlist() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidate = _read_csv(STAGE574_CANDIDATE)
    pairwise = _read_csv(STAGE574_PAIRWISE)
    p0 = candidate[candidate["watch_priority"].astype(str).eq("P0_independent_material")].copy()
    p0_products = p0["product_vt_symbol"].astype(str).tolist()
    route_matrix = _latest_forward_route_matrix(p0_products)

    if not pairwise.empty:
        pairwise["abs_daily_pnl_corr"] = _num(pairwise, "abs_daily_pnl_corr")
        max_pair = []
        for product in p0_products:
            related = pairwise[
                pairwise["left_product"].astype(str).eq(product) | pairwise["right_product"].astype(str).eq(product)
            ]
            max_pair.append(
                {
                    "product_vt_symbol": product,
                    "max_abs_pairwise_corr_in_p0": float(related["abs_daily_pnl_corr"].max()) if not related.empty else 0.0,
                    "most_correlated_p0_peer": (
                        related.sort_values("abs_daily_pnl_corr", ascending=False).iloc[0]["right_product"]
                        if not related.empty
                        and str(related.sort_values("abs_daily_pnl_corr", ascending=False).iloc[0]["left_product"]) == product
                        else (
                            related.sort_values("abs_daily_pnl_corr", ascending=False).iloc[0]["left_product"]
                            if not related.empty
                            else ""
                        )
                    ),
                }
            )
        pair_max = pd.DataFrame(max_pair)
    else:
        pair_max = pd.DataFrame({"product_vt_symbol": p0_products})

    watch = p0.merge(route_matrix, on="product_vt_symbol", how="left").merge(pair_max, on="product_vt_symbol", how="left")
    for col in [
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "abs_core_daily_pnl_corr",
        "single_max_order_volume_to_day_volume_pct",
        "positive_year_rate_pct",
        "route_ready_count",
        "max_abs_pairwise_corr_in_p0",
    ]:
        watch[col] = _num(watch, col)

    watch["selector_gate_status"] = np.where(
        watch["route_ready_count"].ge(MIN_ACTIVE_ROUTES_PER_PRODUCT),
        "collect_forward_labels_only",
        "data_gap_collect_sources_first",
    )
    watch["trading_allowed_now"] = 0
    watch["why_not_trading"] = (
        "Stage561 forward sample depth is not ready; this product may only accumulate point-in-time features and future labels."
    )
    watch["proposed_product_risk_unit_max"] = MAX_PRODUCT_RISK_UNIT
    watch.sort_values(
        ["route_ready_count", "total_pnl", "abs_core_daily_pnl_corr"],
        ascending=[False, False, True],
        inplace=True,
    )
    return watch, route_matrix, pairwise


def build_family_budget(watch: pd.DataFrame) -> pd.DataFrame:
    if watch.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    total_p0 = int(len(watch))
    for family, group in watch.groupby("product_family"):
        p0_count = int(len(group))
        family_budget_pct = min(MAX_FAMILY_BUDGET_PCT, 100.0 * p0_count / max(total_p0, 1))
        same_family_tie_break_required = int(p0_count > 1)
        rows.append(
            {
                "product_family": family,
                "p0_product_count": p0_count,
                "p0_products": ",".join(group["product_vt_symbol"].astype(str).tolist()),
                "historical_p0_pnl_sum": float(group["total_pnl"].sum()),
                "max_abs_core_corr": float(group["abs_core_daily_pnl_corr"].max()),
                "suggested_family_budget_cap_pct": float(family_budget_pct),
                "max_product_risk_unit": MAX_PRODUCT_RISK_UNIT,
                "same_family_tie_break_required": same_family_tie_break_required,
                "tie_break_rule": "same-family same-direction entries require ex-ante selector ranking; no equal add if selector unavailable"
                if same_family_tie_break_required
                else "single P0 product in family",
            }
        )
    return pd.DataFrame(rows).sort_values(["same_family_tie_break_required", "historical_p0_pnl_sum"], ascending=[False, False])


def build_gates(watch: pd.DataFrame, pairwise: pd.DataFrame, family_budget: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    progress = _stage561_progress()
    forward_runs = _parse_progress_int(progress.get("forward_runs_ready_current"))
    forward_dates = _parse_progress_int(progress.get("forward_dates_ready_current"))
    p0_count = int(len(watch))
    avg_pair_abs = float(pairwise["abs_daily_pnl_corr"].mean()) if not pairwise.empty else 0.0
    max_pair_abs = float(pairwise["abs_daily_pnl_corr"].max()) if not pairwise.empty else 0.0
    route_ready_products = int((watch["route_ready_count"] >= MIN_ACTIVE_ROUTES_PER_PRODUCT).sum()) if not watch.empty else 0
    sentiment_ready_products = int(_num(watch, "sentiment_news_manual_event_ready").sum()) if not watch.empty else 0
    tied_families = int(_num(family_budget, "same_family_tie_break_required").sum()) if not family_budget.empty else 0

    rows = [
        {
            "gate": "p0_pool_exists",
            "passed": int(p0_count >= P0_MIN_PRODUCTS),
            "actual": f"{p0_count} P0 products",
            "required": f">={P0_MIN_PRODUCTS}",
            "severity": "hard",
            "judgement": "有足够低相关、容量通过、历史有材料性的观察池。",
        },
        {
            "gate": "p0_pairwise_corr_ok",
            "passed": int(avg_pair_abs <= MAX_AVG_PAIRWISE_ABS_CORR and max_pair_abs <= MAX_PAIRWISE_ABS_CORR),
            "actual": f"avg={avg_pair_abs:.4f}, max={max_pair_abs:.4f}",
            "required": f"avg<={MAX_AVG_PAIRWISE_ABS_CORR}, max<={MAX_PAIRWISE_ABS_CORR}",
            "severity": "hard",
            "judgement": "P0之间当前不呈现高相关拥挤。",
        },
        {
            "gate": "p0_min_two_external_routes",
            "passed": int(route_ready_products >= p0_count and p0_count > 0),
            "actual": f"{route_ready_products}/{p0_count} P0 products",
            "required": f"each P0 has >={MIN_ACTIVE_ROUTES_PER_PRODUCT} ready routes",
            "severity": "hard",
            "judgement": "观察池不能只靠价格历史，至少要有两条点时化外生状态可持续记录。",
        },
        {
            "gate": "p0_sentiment_or_event_coverage",
            "passed": int(sentiment_ready_products >= p0_count and p0_count > 0),
            "actual": f"{sentiment_ready_products}/{p0_count} P0 products",
            "required": "each P0 has real event/news rows before sentiment is used",
            "severity": "soft",
            "judgement": "舆情/事件覆盖不足时，只能作为已有覆盖品种的观察字段，不能做全池 selector。",
        },
        {
            "gate": "same_family_tie_break_predeclared",
            "passed": int(tied_families == 0),
            "actual": f"{tied_families} families require tie-break",
            "required": "0 same-family duplicate P0 groups or frozen tie-break rule",
            "severity": "hard",
            "judgement": "同族多品种不能同时吃满风险，必须靠事前排名或二选一。",
        },
        {
            "gate": "forward_runs_ready",
            "passed": int(forward_runs >= MIN_FORWARD_RUNS),
            "actual": str(forward_runs),
            "required": str(MIN_FORWARD_RUNS),
            "severity": "hard",
            "judgement": "跨日 forward 样本不足前，禁止收益回测化 selector。",
        },
        {
            "gate": "forward_dates_ready",
            "passed": int(forward_dates >= MIN_FORWARD_DATES),
            "actual": str(forward_dates),
            "required": str(MIN_FORWARD_DATES),
            "severity": "hard",
            "judgement": "同日重复采集不能增加样本深度。",
        },
    ]
    gates = pd.DataFrame(rows)
    summary = {
        "forward_runs": forward_runs,
        "forward_dates": forward_dates,
        "p0_count": p0_count,
        "route_ready_products": route_ready_products,
        "sentiment_ready_products": sentiment_ready_products,
        "same_family_tie_break_required_count": tied_families,
        "avg_pairwise_abs_corr": avg_pair_abs,
        "max_pairwise_abs_corr": max_pair_abs,
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_count": int(len(gates)),
    }
    return gates, summary


def write_chart(watch: pd.DataFrame, route_matrix: pd.DataFrame, family_budget: pd.DataFrame, gates: pd.DataFrame, summary: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Stage582 breadth selector operational gate", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    plot_watch = watch.sort_values("total_pnl", ascending=True)
    colors = ["#2f9e44" if x <= 0.05 else "#74c0fc" if x <= 0.15 else "#ffa94d" for x in plot_watch["abs_core_daily_pnl_corr"]]
    ax.barh(plot_watch["product_vt_symbol"], plot_watch["total_pnl"], color=colors)
    ax.set_title("P0 historical materiality; color = core corr bucket")
    ax.set_xlabel("single-product historical pnl")
    for _, row in plot_watch.iterrows():
        ax.text(row["total_pnl"], row["product_vt_symbol"], f" corr {row['abs_core_daily_pnl_corr']:.3f}", va="center", fontsize=8)

    ax = axes[0, 1]
    route_cols = ["basis_ready", "inventory_ready", "sentiment_news_manual_event_ready"]
    if not route_matrix.empty:
        matrix = route_matrix.set_index("product_vt_symbol")[[col for col in route_cols if col in route_matrix.columns]].fillna(0).astype(float)
        im = ax.imshow(matrix.values, vmin=0, vmax=1, cmap="RdYlGn")
        ax.set_xticks(range(len(matrix.columns)))
        ax.set_xticklabels([col.replace("_ready", "") for col in matrix.columns], rotation=25, ha="right")
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels(matrix.index)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, int(matrix.iloc[i, j]), ha="center", va="center", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Point-in-time external route readiness")

    ax = axes[1, 0]
    fam = family_budget.sort_values("historical_p0_pnl_sum", ascending=True)
    ax.barh(fam["product_family"], fam["p0_product_count"], color="#4dabf7")
    ax.set_title("P0 family concentration")
    ax.set_xlabel("P0 product count")
    for _, row in fam.iterrows():
        label = f"cap {row['suggested_family_budget_cap_pct']:.0f}%"
        if int(row["same_family_tie_break_required"]):
            label += " / tie-break"
        ax.text(row["p0_product_count"], row["product_family"], label, va="center", fontsize=8)

    ax = axes[1, 1]
    gate_plot = gates.copy()
    gate_plot["value"] = np.where(gate_plot["passed"].astype(int).eq(1), 1.0, 0.0)
    ax.barh(gate_plot["gate"], gate_plot["value"], color=np.where(gate_plot["passed"].astype(int).eq(1), "#2f9e44", "#e03131"))
    ax.set_xlim(0, 1)
    ax.set_title(
        f"Gate pass {summary['gate_pass_count']}/{summary['gate_count']} | forward {summary['forward_runs']}/{MIN_FORWARD_RUNS} runs"
    )
    for idx, row in gate_plot.iterrows():
        ax.text(0.03, idx, row["actual"], va="center", color="white" if row["passed"] else "black", fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    watch: pd.DataFrame,
    family_budget: pd.DataFrame,
    gates: pd.DataFrame,
    summary: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    references = [
        "Trend-following trading strategies in commodity futures: A re-examination, Journal of Banking & Finance, 2010.",
        "Optimal allocation of trend following strategies, Physica A, 2015.",
        "Rob Carver / pysystemtrade instrument diversification and correlation engineering notes.",
        "Portfolio stress testing applied to commodity futures, Computational Management Science, 2020.",
    ]
    text = f"""# Stage582 breadth selector operational gate

Generated: {decision["generated_at_cst"]} CST

## Decision

- decision: `{decision["decision"]}`
- gate: `{summary["gate_pass_count"]}/{summary["gate_count"]}`
- P0 products: `{summary["p0_count"]}`
- forward runs/dates: `{summary["forward_runs"]}/{MIN_FORWARD_RUNS}`, `{summary["forward_dates"]}/{MIN_FORWARD_DATES}`
- route-ready P0 products: `{summary["route_ready_products"]}/{summary["p0_count"]}`
- sentiment/event-ready P0 products: `{summary["sentiment_ready_products"]}/{summary["p0_count"]}`

## Research judgement

本阶段不生成交易候选、不做收益回测、不修改 Stage526。它把“低单笔风险、扩池、避高相关、选对品种”从想法落成当前可执行 gate：先允许 P0 品种继续积累 point-in-time 外生状态和未来 63/126 日标签；在 Stage561 的 `20/20` 跨日样本未达标前，不允许把 P0 历史赢家变成交易白名单。

外部资料支持多市场趋势、风险预算和相关性治理，但不支持样本内赢家筛选。我的判断是：方向继续有效，当前仍卡在 selector 证据，不卡在品种数量。

## Watchlist

{_md_table(watch, [
    "product_vt_symbol",
    "product_family",
    "total_pnl",
    "max_dd_pct",
    "sharpe",
    "abs_core_daily_pnl_corr",
    "max_abs_pairwise_corr_in_p0",
    "route_ready_count",
    "ready_routes",
    "selector_gate_status",
], 20)}

## Family budget

{_md_table(family_budget, [
    "product_family",
    "p0_product_count",
    "p0_products",
    "suggested_family_budget_cap_pct",
    "same_family_tie_break_required",
    "tie_break_rule",
], 20)}

## Gates

{_md_table(gates, max_rows=20)}

## References

""" + "\n".join(f"- {item}" for item in references) + "\n"
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    watch, route_matrix, pairwise = build_watchlist()
    family_budget = build_family_budget(watch)
    gates, summary = build_gates(watch, pairwise, family_budget)
    hard = gates[gates["severity"].eq("hard")]
    decision_label = (
        "breadth_selector_probe_allowed"
        if not hard.empty and int(hard["passed"].sum()) == len(hard)
        else "breadth_selector_operational_gate_not_ready"
    )
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "summary": summary,
        "p0_products": watch["product_vt_symbol"].astype(str).tolist(),
        "no_backtest": True,
        "strategy_changed": False,
        "promotion_allowed": decision_label == "breadth_selector_probe_allowed",
        "overfit_assessment": "not overfit: no parameter sweep, no historical whitelist promotion, only point-in-time readiness gating",
        "continue_value": "yes: selector evidence is still the bottleneck and can be improved by forward collection without changing trading rules",
    }

    watch.to_csv(WATCHLIST_PATH, index=False, encoding="utf-8-sig")
    route_matrix.to_csv(ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    family_budget.to_csv(FAMILY_BUDGET_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(watch, route_matrix, family_budget, gates, summary)
    write_report(watch, family_budget, gates, summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

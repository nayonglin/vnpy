from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage525_maxpos4_cash_boundary_v1"
OUTPUT_PREFIX = "qmt_roll_stage525_maxpos4_cash_boundary"

STAGE524_TAG = "stage524_surgical_peak_margin_frontier_v1"
STAGE524_PREFIX = "qmt_roll_stage524_surgical_peak_margin_frontier"
STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

STAGE524_DAILY_IN = OUTPUT_DIR / f"{STAGE524_PREFIX}_margin_daily_{STAGE524_TAG}.csv"
STAGE524_SUMMARY_IN = OUTPUT_DIR / f"{STAGE524_PREFIX}_summary_{STAGE524_TAG}.csv"
STAGE520_SUMMARY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_summary_{STAGE520_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ACCOUNT_CAPITAL = 615_000.0
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
BASE_VARIANTS: tuple[str, ...] = ("r080_pc30_maxpos4", "r080_pc30_maxpos5", "r080_pc30_control")
REFERENCE_VARIANTS: tuple[str, ...] = ("r080_pc25_u75", "r070_pc30_u75")


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


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    values = equity.astype(float)
    peak = values.cummax()
    dd = values / peak.replace(0.0, np.nan) - 1.0
    return float(dd.min() * 100.0)


def _ulcer_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    values = equity.astype(float)
    peak = values.cummax().replace(0.0, np.nan)
    dd = ((values / peak) - 1.0).clip(upper=0.0) * 100.0
    return float(np.sqrt(np.nanmean(np.square(dd.to_numpy(dtype=float)))))


def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(252.0))


def _cash_required(frame: pd.DataFrame, margin_line: float) -> float:
    line = max(1e-9, float(margin_line))
    required = frame["broker10_total_margin_exact"].astype(float) / line - frame["account_equity"].astype(float)
    return float(required.clip(lower=0.0).max())


def _cash_scenarios(frame: pd.DataFrame) -> list[tuple[str, float]]:
    exact_100 = _cash_required(frame, 1.0)
    exact_95 = _cash_required(frame, 0.95)
    exact_90 = _cash_required(frame, 0.90)
    rounded_100 = math.ceil(exact_100 / 10_000.0) * 10_000.0 if exact_100 > 0 else 0.0
    return [
        ("cash0", 0.0),
        ("cash_req_broker100", exact_100),
        ("cash_round10k_broker100", rounded_100),
        ("cash_req_broker95", exact_95),
        ("cash_req_broker90", exact_90),
    ]


def _metrics(frame: pd.DataFrame, *, base_variant: str, cash_label: str, extra_cash: float, cost_multiplier: float) -> dict[str, Any]:
    ordered = frame.sort_values("date").copy()
    additional = ordered["total_slippage"].astype(float).cumsum() * max(0.0, float(cost_multiplier) - 1.0)
    equity = pd.Series(
        ordered["account_equity"].astype(float).to_numpy() + float(extra_cash) - additional.to_numpy(),
        index=pd.to_datetime(ordered["date"]),
    )
    initial_capital = ACCOUNT_CAPITAL + float(extra_cash)
    end_equity = float(equity.iloc[-1])
    total_profit = end_equity - initial_capital
    margin_ratio = ordered["broker10_total_margin_exact"].astype(float).to_numpy() / np.maximum(equity.to_numpy(dtype=float), 1e-9) * 100.0
    nonzero_pnl = ordered["total_net_pnl"].astype(float)
    nonzero_pnl = nonzero_pnl[nonzero_pnl.abs() > 1e-12]
    return {
        "base_variant": base_variant,
        "cash_label": cash_label,
        "cost_multiplier": float(cost_multiplier),
        "extra_cash": float(extra_cash),
        "initial_capital": initial_capital,
        "end_equity": end_equity,
        "deployment_return_pct": total_profit / initial_capital * 100.0 if initial_capital > 0 else 0.0,
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "sharpe": _sharpe(equity),
        "max_broker10_margin_to_equity_pct": float(np.max(margin_ratio)) if len(margin_ratio) else 0.0,
        "days_over_100pct": int(np.sum(margin_ratio > 100.0 + 1e-9)),
        "days_over_95pct": int(np.sum(margin_ratio > 95.0 + 1e-9)),
        "days_over_90pct": int(np.sum(margin_ratio > 90.0 + 1e-9)),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum() + ordered["xsmom_true_held_contract_count"].diff().abs().fillna(0.0).sum()),
        "nonzero_daily_win_rate_pct": float((nonzero_pnl > 0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "dd40_pass": int(_max_drawdown_pct(equity) >= -40.0),
        "broker10_100_pass": int(np.all(margin_ratio <= 100.0 + 1e-9)) if len(margin_ratio) else 1,
    }


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


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, reference: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index(["base_variant", "cash_label"])
    ranked: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        item = row._asdict()
        key = (str(item["base_variant"]), str(item["cash_label"]))
        two = cost2.loc[key] if key in cost2.index else None
        two_x_dd = _safe_float(two["max_dd_pct"]) if two is not None else 0.0
        hard_pass = int(int(item["broker10_100_pass"]) == 1 and int(item["dd40_pass"]) == 1 and two_x_dd >= -40.0)
        ranked.append({**item, "two_x_max_dd_pct": two_x_dd, "hard_pass": hard_pass})
    ranked = sorted(ranked, key=lambda item: (item["hard_pass"], item["deployment_return_pct"]), reverse=True)
    best_hard = ranked[0] if ranked else {}
    ref_map = reference.set_index("variant")["total_return_pct"].to_dict()
    r080_u75 = _safe_float(ref_map.get("r080_pc25_u75"))
    r070_u75 = _safe_float(ref_map.get("r070_pc30_u75"))
    best_return = _safe_float(best_hard.get("deployment_return_pct"))
    if best_hard and int(best_hard.get("hard_pass", 0)) == 1 and best_return > r080_u75:
        label = "cash_boundary_capital_efficiency_upgrade"
    elif best_hard and int(best_hard.get("hard_pass", 0)) == 1 and best_return > r070_u75:
        label = "cash_boundary_only_middle_candidate"
    else:
        label = "cash_boundary_no_capital_efficiency_upgrade"
    return {
        "decision": label,
        "best_hard": best_hard,
        "reference_r080_pc25_u75_return_pct": r080_u75,
        "reference_r070_pc30_u75_return_pct": r070_u75,
        "ranked": ranked,
    }


def _plot(summary: pd.DataFrame, reference: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    ax_ret, ax_margin = axes
    view = summary[summary["base_variant"].eq("r080_pc30_maxpos4")].sort_values("extra_cash")
    ax_ret.plot(view["extra_cash"], view["deployment_return_pct"], marker="o", label="maxpos4 cash")
    for variant in REFERENCE_VARIANTS:
        ref = reference[reference["variant"].eq(variant)]
        if not ref.empty:
            ax_ret.axhline(float(ref["total_return_pct"].iloc[0]), linestyle="--", linewidth=1, label=variant)
    ax_ret.set_title("部署收益率 vs 现金")
    ax_ret.set_xlabel("extra cash")
    ax_ret.set_ylabel("%")
    ax_ret.grid(alpha=0.25)
    ax_ret.legend(fontsize=8)

    ax_margin.plot(view["extra_cash"], view["max_broker10_margin_to_equity_pct"], marker="o", color="#dc2626")
    ax_margin.axhline(100, linestyle="--", linewidth=1, color="#111827")
    ax_margin.set_title("broker10保证金/权益 vs 现金")
    ax_margin.set_xlabel("extra cash")
    ax_margin.set_ylabel("%")
    ax_margin.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, reference: pd.DataFrame, decision: dict[str, Any]) -> None:
    view = summary[
        [
            "base_variant",
            "cash_label",
            "extra_cash",
            "initial_capital",
            "deployment_return_pct",
            "max_dd_pct",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
            "sharpe",
        ]
    ].sort_values(["base_variant", "extra_cash"])
    lines = [
        "# Stage525 maxpos4现金边界审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：部署资金边界转换；不改策略、不改信号、不新增交易规则。",
        f"- 决策：`{decision.get('decision', '')}`。",
        "",
        "## 参考硬通过壳",
        "",
        _md_table(reference[["variant", "total_return_pct", "max_dd_pct", "sharpe", "max_broker10_margin_to_equity_pct"]]),
        "",
        "## 现金边界",
        "",
        _md_table(view),
        "",
        "## 2x/3x成本摘要",
        "",
        _md_table(
            cost[
                [
                    "base_variant",
                    "cash_label",
                    "cost_multiplier",
                    "deployment_return_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                ]
            ].sort_values(["base_variant", "cash_label", "cost_multiplier"]),
            max_rows=30,
        ),
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 判断",
        "",
        "- 若压到 broker100 后部署收益率仍低于 `r080_pc25_u75`，则它不是当前资本效率主候选。",
        "- 若只高于 `r070_pc30_u75`，最多算中间候选或资金更充裕账户的 paper 对照。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    daily = pd.read_csv(STAGE524_DAILY_IN, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "broker10_total_margin_exact", "total_slippage", "total_net_pnl", "trade_count", "xsmom_true_held_contract_count"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    reference = pd.read_csv(STAGE520_SUMMARY_IN, encoding="utf-8-sig")
    reference = reference[reference["variant"].isin(REFERENCE_VARIANTS)].copy()
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for base_variant in BASE_VARIANTS:
        frame = daily[daily["variant"].eq(base_variant)].copy()
        if frame.empty:
            continue
        for cash_label, extra_cash in _cash_scenarios(frame):
            for cost_multiplier in COST_MULTIPLIERS:
                row = _metrics(frame, base_variant=base_variant, cash_label=cash_label, extra_cash=extra_cash, cost_multiplier=cost_multiplier)
                cost_rows.append(row)
                if cost_multiplier == 1.0:
                    summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    decision = _decision(summary, cost, reference)
    _plot(summary, reference)
    _write_report(summary, cost, reference, decision)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

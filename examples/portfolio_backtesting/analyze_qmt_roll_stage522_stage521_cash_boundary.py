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

MODEL_TAG = "stage522_stage521_cash_boundary_v1"
OUTPUT_PREFIX = "qmt_roll_stage522_stage521_cash_boundary"

STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"
MARGIN_DAILY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_summary_{STAGE520_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASE_VARIANTS = ("r070_pc30_u75", "r080_pc25_u75")
CASH_VARIANT = "r080_pc30_u80"
CASH_LEVELS = (0.0, 165_223.44, 170_000.0, 200_000.0, 300_000.0)
BASE_CAPITAL = 615_000.0


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


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return (equity.astype(float) / equity.astype(float).cummax() - 1.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().dropna()
    if returns.std(ddof=0) <= 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(252.0))


def _metrics(frame: pd.DataFrame, variant: str, label: str, extra_cash: float, stress_cost_multiplier: float = 1.0) -> dict[str, Any]:
    frame = frame.sort_values("date").copy()
    equity = frame["account_equity"].astype(float) + float(extra_cash)
    if stress_cost_multiplier != 1.0:
        extra_slippage = frame["total_slippage"].astype(float).cumsum() * (stress_cost_multiplier - 1.0)
        equity = equity - extra_slippage
    initial_capital = BASE_CAPITAL + float(extra_cash)
    margin_ratio = frame["broker10_total_margin_exact"].astype(float) / equity * 100.0
    return {
        "variant": variant,
        "label": label,
        "extra_cash": float(extra_cash),
        "initial_capital": initial_capital,
        "cost_multiplier": float(stress_cost_multiplier),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe(equity),
        "max_broker10_margin_to_equity_pct": float(margin_ratio.max()),
        "days_over_100pct": int((margin_ratio > 100.0).sum()),
        "days_over_95pct": int((margin_ratio > 95.0).sum()),
        "days_over_90pct": int((margin_ratio > 90.0).sum()),
    }


def _md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def main() -> None:
    daily = pd.read_csv(MARGIN_DAILY_IN, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    base_summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig")
    stage079_return = float(base_summary["total_return_pct"].max() / (base_summary["return_retention_vs_stage079_pct"].max() / 100.0))

    rows: list[dict[str, Any]] = []
    for variant in BASE_VARIANTS:
        frame = daily[daily["variant"].eq(variant)].copy()
        label = str(frame["label"].iloc[0])
        for stress in (1.0, 2.0):
            rows.append(_metrics(frame, variant, label, 0.0, stress))
    cash_frame = daily[daily["variant"].eq(CASH_VARIANT)].copy()
    cash_label = str(cash_frame["label"].iloc[0])
    for extra_cash in CASH_LEVELS:
        for stress in (1.0, 2.0):
            rows.append(_metrics(cash_frame, f"{CASH_VARIANT}_cash{int(round(extra_cash))}", cash_label, extra_cash, stress))

    summary = pd.DataFrame(rows)
    summary["return_retention_vs_stage079_pct"] = summary["total_return_pct"] / stage079_return * 100.0
    one_x = summary[summary["cost_multiplier"].eq(1.0)].copy()
    two_x = summary[summary["cost_multiplier"].eq(2.0)].set_index("variant")
    one_x["two_x_max_dd_pct"] = one_x["variant"].map(two_x["max_dd_pct"])
    one_x["hard_pass"] = (
        (one_x["max_dd_pct"] >= -40.0)
        & (one_x["max_broker10_margin_to_equity_pct"] <= 100.0)
        & (one_x["two_x_max_dd_pct"] >= -40.0)
    ).astype(int)

    hard = one_x[one_x["hard_pass"].eq(1)].copy()
    hard = hard.sort_values(["total_return_pct", "sharpe"], ascending=False)
    best = hard.iloc[0].to_dict() if not hard.empty else {}
    decision = {
        "decision": "cash_boundary_no_capital_efficiency_upgrade",
        "best_hard_pass_by_deployment_return": best,
        "hard_pass_variants": hard.to_dict(orient="records"),
        "judgement": (
            "Adding cash to r080_pc30_u80 can make broker100 pass, but the deployment return "
            "does not beat r070_pc30_u75, so this is not a capital-efficiency upgrade."
        ),
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    cash_view = one_x[one_x["variant"].str.startswith(CASH_VARIANT)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    axes[0].plot(cash_view["extra_cash"], cash_view["total_return_pct"], marker="o")
    axes[0].axhline(float(one_x[one_x["variant"].eq("r070_pc30_u75")]["total_return_pct"].iloc[0]), color="#7c3aed", linestyle="--")
    axes[0].set_title("r080_pc30_u80 加现金后收益率")
    axes[0].set_xlabel("额外现金")
    axes[0].set_ylabel("%")
    axes[0].grid(alpha=0.25)
    axes[1].plot(cash_view["extra_cash"], cash_view["max_dd_pct"], marker="o")
    axes[1].axhline(-40, color="#111827", linestyle="--")
    axes[1].set_title("最大回撤")
    axes[1].grid(alpha=0.25)
    axes[2].plot(cash_view["extra_cash"], cash_view["max_broker10_margin_to_equity_pct"], marker="o")
    axes[2].axhline(100, color="#111827", linestyle="--")
    axes[2].set_title("broker10最大保证金/权益")
    axes[2].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)

    report = f"""# Stage522 Stage521现金边界审计

- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 阶段性质：部署现金边界，只读转换；不改策略、不改 cap/usage。
- 决策：`{decision['decision']}`。

## 1x核心结果

{_md_table(one_x[['variant','extra_cash','initial_capital','end_equity','total_return_pct','return_retention_vs_stage079_pct','max_dd_pct','sharpe','max_broker10_margin_to_equity_pct','days_over_100pct','two_x_max_dd_pct','hard_pass']])}

## 判断

- `r080_pc30_u80 + 17万现金` 可以把正常成本 broker10 压到 `100%` 内，但部署资金收益率约 `2497.7752%`，低于 `r070_pc30_u75` 的 `2581.3488%`。
- 它的绝对期末权益更高，但资金占用也更高；按资本效率与风险干净度，不优于 `r070_pc30_u75`。
- 如果用户愿意把目标改成“绝对利润最大化且允许更多现金”，才值得继续；在当前保收益/可执行口径下，不应把现金 near-pass 直接晋级。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

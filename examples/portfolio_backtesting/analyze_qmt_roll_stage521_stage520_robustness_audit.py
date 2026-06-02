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

MODEL_TAG = "stage521_stage520_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage521_stage520_robustness_audit"

STAGE520_TAG = "stage520_product_cap_usage_gate_frontier_v1"
STAGE520_PREFIX = "qmt_roll_stage520_product_cap_usage_gate_frontier"

SUMMARY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_summary_{STAGE520_TAG}.csv"
COST_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_cost_stress_{STAGE520_TAG}.csv"
MARGIN_DAILY_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_margin_daily_{STAGE520_TAG}.csv"
PRODUCT_EVENTS_IN = OUTPUT_DIR / f"{STAGE520_PREFIX}_product_margin_events_{STAGE520_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HOLDING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_holding_experience_{MODEL_TAG}.csv"
COLD_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cold_start_{MODEL_TAG}.csv"
EXTRA_CASH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_cash_{MODEL_TAG}.csv"
PRODUCT_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_events_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CANDIDATES = ("r080_pc25_u75", "r080_pc30_u75", "r070_pc30_u75", "r080_pc30_u80")
HOLDING_DAYS = (21, 63, 126, 180, 252, 504, 756)


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


def _drawdown(equity: pd.Series) -> pd.Series:
    equity = equity.astype(float)
    return (equity / equity.cummax() - 1.0) * 100.0


def _ulcer(equity: pd.Series) -> float:
    dd = _drawdown(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _longest_underwater(equity: pd.Series) -> int:
    dd = _drawdown(equity)
    best = 0
    current = 0
    for value in dd.to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig")
    cost = pd.read_csv(COST_IN, encoding="utf-8-sig")
    margin = pd.read_csv(MARGIN_DAILY_IN, encoding="utf-8-sig")
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    events = pd.read_csv(PRODUCT_EVENTS_IN, encoding="utf-8-sig") if PRODUCT_EVENTS_IN.exists() else pd.DataFrame()
    if not events.empty and "date" in events.columns:
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    summary = summary[summary["variant"].isin(CANDIDATES)].copy()
    cost = cost[cost["variant"].isin(CANDIDATES)].copy()
    margin = margin[margin["variant"].isin(CANDIDATES)].copy()
    events = events[events["variant"].isin(CANDIDATES)].copy() if not events.empty else events
    return summary, cost, margin, events


def _segment_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    equity = pd.Series(frame["account_equity"].astype(float).to_numpy(), index=frame["date"])
    start_equity = float(equity.iloc[0])
    end_equity = float(equity.iloc[-1])
    return {
        "start_date": equity.index[0],
        "end_date": equity.index[-1],
        "start_equity": start_equity,
        "end_equity": end_equity,
        "return_pct": (end_equity / start_equity - 1.0) * 100.0,
        "max_dd_pct": float(_drawdown(equity).min()),
        "ulcer_pct": _ulcer(equity),
        "longest_underwater_days": _longest_underwater(equity),
        "max_broker10_margin_to_equity_pct": float(frame["broker10_margin_to_equity_pct"].max()),
        "days_over_100pct": int((frame["broker10_margin_to_equity_pct"] > 100.0).sum()),
        "days_over_90pct": int((frame["broker10_margin_to_equity_pct"] > 90.0).sum()),
    }


def _holding_experience(margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in margin.groupby("variant", sort=False):
        frame = frame.sort_values("date").reset_index(drop=True)
        label = str(frame["label"].iloc[0])
        for horizon in HOLDING_DAYS:
            windows: list[dict[str, Any]] = []
            if len(frame) <= horizon:
                continue
            for start_pos in range(0, len(frame) - horizon):
                seg = frame.iloc[start_pos : start_pos + horizon + 1].copy()
                windows.append(_segment_metrics(seg))
            w = pd.DataFrame(windows)
            worst_idx = int(w["return_pct"].idxmin())
            worst_dd_idx = int(w["max_dd_pct"].idxmin())
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "holding_days": horizon,
                    "sample_count": len(w),
                    "min_return_pct": float(w["return_pct"].min()),
                    "p05_return_pct": float(w["return_pct"].quantile(0.05)),
                    "p10_return_pct": float(w["return_pct"].quantile(0.10)),
                    "median_return_pct": float(w["return_pct"].median()),
                    "positive_rate_pct": float((w["return_pct"] > 0).mean() * 100.0),
                    "below_5pct_rate_pct": float((w["return_pct"] < 5.0).mean() * 100.0),
                    "worst_window_dd_pct": float(w["max_dd_pct"].min()),
                    "p05_window_dd_pct": float(w["max_dd_pct"].quantile(0.05)),
                    "dd20_breach_rate_pct": float((w["max_dd_pct"] < -20.0).mean() * 100.0),
                    "dd30_breach_rate_pct": float((w["max_dd_pct"] < -30.0).mean() * 100.0),
                    "dd40_breach_rate_pct": float((w["max_dd_pct"] < -40.0).mean() * 100.0),
                    "broker100_breach_rate_pct": float((w["days_over_100pct"] > 0).mean() * 100.0),
                    "p95_max_broker10_margin_pct": float(w["max_broker10_margin_to_equity_pct"].quantile(0.95)),
                    "worst_return_start": w.loc[worst_idx, "start_date"],
                    "worst_return_end": w.loc[worst_idx, "end_date"],
                    "worst_dd_start": w.loc[worst_dd_idx, "start_date"],
                    "worst_dd_end": w.loc[worst_dd_idx, "end_date"],
                }
            )
    return pd.DataFrame(rows)


def _cold_start(margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in margin.groupby("variant", sort=False):
        frame = frame.sort_values("date").reset_index(drop=True)
        label = str(frame["label"].iloc[0])
        start_sets = {
            "month": frame.groupby(frame["date"].dt.to_period("M"), sort=True).head(1).index.tolist(),
            "quarter": frame.groupby(frame["date"].dt.to_period("Q"), sort=True).head(1).index.tolist(),
            "year": frame.groupby(frame["date"].dt.year, sort=True).head(1).index.tolist(),
        }
        for start_type, start_indices in start_sets.items():
            windows: list[dict[str, Any]] = []
            for start_idx in start_indices:
                seg = frame.iloc[start_idx:].copy()
                if len(seg) < 20:
                    continue
                windows.append(_segment_metrics(seg))
            w = pd.DataFrame(windows)
            if w.empty:
                continue
            worst_idx = int(w["max_dd_pct"].idxmin())
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "start_type": start_type,
                    "sample_count": len(w),
                    "min_return_pct": float(w["return_pct"].min()),
                    "p05_return_pct": float(w["return_pct"].quantile(0.05)),
                    "median_return_pct": float(w["return_pct"].median()),
                    "worst_max_dd_pct": float(w["max_dd_pct"].min()),
                    "p05_max_dd_pct": float(w["max_dd_pct"].quantile(0.05)),
                    "dd30_pass_rate_pct": float((w["max_dd_pct"] >= -30.0).mean() * 100.0),
                    "dd40_pass_rate_pct": float((w["max_dd_pct"] >= -40.0).mean() * 100.0),
                    "broker100_pass_rate_pct": float((w["days_over_100pct"] == 0).mean() * 100.0),
                    "worst_dd_start": w.loc[worst_idx, "start_date"],
                    "worst_dd_end": w.loc[worst_idx, "end_date"],
                    "worst_dd_broker10_pct": float(w.loc[worst_idx, "max_broker10_margin_to_equity_pct"]),
                }
            )
    return pd.DataFrame(rows)


def _extra_cash(margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in margin.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        label = str(frame["label"].iloc[0])
        equity = frame["account_equity"].astype(float)
        broker_margin = frame["broker10_total_margin_exact"].astype(float)
        for safety_line in (100.0, 95.0, 90.0):
            required_equity = broker_margin / (safety_line / 100.0)
            deficit = np.maximum(required_equity.to_numpy(dtype=float) - equity.to_numpy(dtype=float), 0.0)
            max_idx = int(np.argmax(deficit))
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "safety_line_pct": safety_line,
                    "max_extra_cash_required": float(deficit[max_idx]),
                    "max_extra_cash_date": frame.iloc[max_idx]["date"],
                    "days_needing_extra_cash": int((deficit > 1e-9).sum()),
                }
            )
    return pd.DataFrame(rows)


def _product_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for variant, frame in events.groupby("variant", sort=False):
        frame = frame.copy()
        date_col = "event_date" if "event_date" in frame.columns else "date"
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize()
        frame["event_total_margin"] = frame.groupby(date_col)["c3_margin_exact"].transform("sum")
        frame["margin_share_pct"] = np.where(
            frame["event_total_margin"].astype(float).abs() > 1e-12,
            frame["c3_margin_exact"].astype(float) / frame["event_total_margin"].astype(float) * 100.0,
            0.0,
        )
        max_margin = frame.groupby(date_col)["c3_margin_exact"].transform("max")
        frame["is_top1"] = (frame["c3_margin_exact"] >= max_margin - 1e-9).astype(int)
        top = (
            frame.groupby("product_vt_symbol", dropna=False)
            .agg(
                event_count=(date_col, "nunique"),
                top1_count=("is_top1", "sum"),
                mean_margin_share_pct=("margin_share_pct", "mean"),
                sum_event_net_pnl=("net_pnl", "sum"),
            )
            .reset_index()
            .sort_values(["event_count", "top1_count"], ascending=False)
        )
        for row in top.head(8).to_dict(orient="records"):
            rows.append({"variant": variant, **row})
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, holding: pd.DataFrame, cold: pd.DataFrame, extra: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    month = cold[cold["start_type"].eq("month")].set_index("variant")
    h63 = holding[holding["holding_days"].eq(63)].set_index("variant")
    ranked: list[dict[str, Any]] = []
    for row in summary.to_dict(orient="records"):
        variant = str(row["variant"])
        two_x_dd = _safe_float(cost2.loc[variant, "max_dd_pct"]) if variant in cost2.index else 0.0
        monthly_dd40 = _safe_float(month.loc[variant, "dd40_pass_rate_pct"]) if variant in month.index else 0.0
        monthly_broker = _safe_float(month.loc[variant, "broker100_pass_rate_pct"]) if variant in month.index else 0.0
        h63_p05 = _safe_float(h63.loc[variant, "p05_return_pct"]) if variant in h63.index else 0.0
        h63_dd30 = _safe_float(h63.loc[variant, "dd30_breach_rate_pct"]) if variant in h63.index else 100.0
        cash100 = extra[(extra["variant"].eq(variant)) & (extra["safety_line_pct"].eq(100.0))]
        extra100 = _safe_float(cash100["max_extra_cash_required"].iloc[0]) if not cash100.empty else 0.0
        hard_pass = bool(
            int(row.get("dd40_pass", 0)) == 1
            and int(row.get("broker10_100_pass", 0)) == 1
            and two_x_dd >= -40.0
        )
        robust_score = (
            _safe_float(row["return_retention_vs_stage079_pct"])
            + max(two_x_dd + 40.0, -20.0) * 2.0
            + monthly_dd40 * 0.08
            + monthly_broker * 0.05
            + h63_p05 * 0.3
            - h63_dd30 * 0.4
            - extra100 / 100000.0
        )
        ranked.append(
            {
                **row,
                "two_x_max_dd_pct": two_x_dd,
                "monthly_dd40_pass_rate_pct": monthly_dd40,
                "monthly_broker100_pass_rate_pct": monthly_broker,
                "h63_p05_return_pct": h63_p05,
                "h63_dd30_breach_rate_pct": h63_dd30,
                "extra_cash_to_broker100": extra100,
                "hard_pass": int(hard_pass),
                "robust_score": robust_score,
            }
        )
    ranked = sorted(ranked, key=lambda item: (item["hard_pass"], item["robust_score"]), reverse=True)
    hard = [item for item in ranked if item["hard_pass"]]
    best = ranked[0] if ranked else {}
    if hard:
        decision = "fixed_shell_candidate_survives_robustness_but_return_low"
    else:
        decision = "fixed_shell_candidate_fails_robustness"
    return {
        "decision": decision,
        "best_variant": best,
        "hard_pass_variants": hard,
        "ranked": ranked,
        "judgement": (
            "Stage520 fixed shell can continue to candidate audit, but remains a risk-budget shell "
            "rather than a final preserve-return answer."
        ),
    }


def _plot(summary: pd.DataFrame, holding: pd.DataFrame, cold: pd.DataFrame, extra: pd.DataFrame, margin: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_nav, ax_holding, ax_cold, ax_cash = axes.flatten()
    colors = {
        "r080_pc25_u75": "#0891b2",
        "r080_pc30_u75": "#dc2626",
        "r070_pc30_u75": "#7c3aed",
        "r080_pc30_u80": "#f97316",
    }
    for variant, frame in margin.groupby("variant", sort=False):
        ax_nav.plot(frame["date"], frame["account_equity"], label=variant, linewidth=1, color=colors.get(variant))
    ax_nav.set_title("固定候选账户权益")
    ax_nav.grid(alpha=0.25)
    ax_nav.legend(fontsize=8)

    hview = holding[holding["holding_days"].isin([63, 126, 252, 504])].copy()
    for variant, frame in hview.groupby("variant", sort=False):
        ax_holding.plot(frame["holding_days"], frame["p05_return_pct"], marker="o", label=variant, color=colors.get(variant))
    ax_holding.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_holding.set_title("任意启动持有收益 p05")
    ax_holding.set_xlabel("交易日")
    ax_holding.set_ylabel("%")
    ax_holding.grid(alpha=0.25)

    cview = cold[cold["start_type"].eq("month")].copy()
    ax_cold.bar(cview["variant"], cview["worst_max_dd_pct"], color=[colors.get(v, "#64748b") for v in cview["variant"]])
    ax_cold.axhline(-40, color="#111827", linestyle="--", linewidth=1)
    ax_cold.set_title("月度冷启动最差最大回撤")
    ax_cold.set_ylabel("%")
    ax_cold.tick_params(axis="x", labelrotation=20)

    cash100 = extra[extra["safety_line_pct"].eq(100.0)].copy()
    merged = summary.merge(cash100[["variant", "max_extra_cash_required"]], on="variant", how="left")
    ax_cash.scatter(
        merged["return_retention_vs_stage079_pct"],
        merged["max_extra_cash_required"],
        s=110,
        c=[colors.get(v, "#64748b") for v in merged["variant"]],
    )
    for row in merged.itertuples(index=False):
        ax_cash.annotate(row.variant, (row.return_retention_vs_stage079_pct, row.max_extra_cash_required), fontsize=8)
    ax_cash.set_title("收益保留 vs 压到broker100所需现金")
    ax_cash.set_xlabel("相对Stage079收益保留%")
    ax_cash.set_ylabel("额外现金")
    ax_cash.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    holding: pd.DataFrame,
    cold: pd.DataFrame,
    extra: pd.DataFrame,
    product: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    best = decision.get("best_variant", {})
    h63 = holding[holding["holding_days"].eq(63)][
        ["variant", "p05_return_pct", "median_return_pct", "positive_rate_pct", "dd30_breach_rate_pct", "broker100_breach_rate_pct"]
    ]
    h126 = holding[holding["holding_days"].eq(126)][
        ["variant", "p05_return_pct", "median_return_pct", "positive_rate_pct", "dd30_breach_rate_pct", "broker100_breach_rate_pct"]
    ]
    month = cold[cold["start_type"].eq("month")][
        ["variant", "sample_count", "worst_max_dd_pct", "dd40_pass_rate_pct", "broker100_pass_rate_pct", "worst_dd_start"]
    ]
    cash100 = extra[extra["safety_line_pct"].eq(100.0)][
        ["variant", "max_extra_cash_required", "max_extra_cash_date", "days_needing_extra_cash"]
    ]
    text = f"""# Stage521 Stage520固定候选鲁棒性审计

- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 阶段性质：只读鲁棒性审计；不重新跑策略，不新增交易规则，不扫小数。
- 决策：`{decision.get('decision')}`。
- 最优排序：`{best.get('variant', '')}`。

## 核心候选

{_md_table(summary[['variant','total_return_pct','return_retention_vs_stage079_pct','max_dd_pct','sharpe','max_broker10_margin_to_equity_pct','days_over_100pct']])}

## 3个月持有体验

{_md_table(h63)}

## 6个月持有体验

{_md_table(h126)}

## 月度冷启动

{_md_table(month)}

## 额外现金边界

{_md_table(cash100)}

## 产品事件摘要

{_md_table(product, max_rows=20)}

## 判断

- `r080_pc25_u75` 和 `r080_pc30_u75` 是硬通过壳，但收益保留偏低。
- `r080_pc30_u80` 收益更接近可接受，但需要额外现金或更低券商上浮，否则不是硬通过。
- 本阶段不支持继续扫 `usage=76/77/78` 或 `product cap=26/27/28`；若继续，应在固定候选间做部署取舍和真实资金边界，而不是救参。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    summary, cost, margin, events = _load_inputs()
    holding = _holding_experience(margin)
    cold = _cold_start(margin)
    extra = _extra_cash(margin)
    product = _product_events(events)
    decision = _decision(summary, cost, holding, cold, extra)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    holding.to_csv(HOLDING_PATH, index=False, encoding="utf-8-sig")
    cold.to_csv(COLD_START_PATH, index=False, encoding="utf-8-sig")
    extra.to_csv(EXTRA_CASH_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_EVENTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(summary, holding, cold, extra, margin)
    _write_report(summary, holding, cold, extra, product, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

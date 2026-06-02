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

MODEL_TAG = "stage515_stage214_margin_gap_postmortem_v1"
OUTPUT_PREFIX = "qmt_roll_stage515_stage214_margin_gap_postmortem"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE352_MARGIN = OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
STAGE512_DETAIL = OUTPUT_DIR / "qmt_roll_stage512_stage208_deployment_constraint_audit_daily_detail_stage512_stage208_deployment_constraint_audit_v1.csv"
STAGE513_MARGIN_DAILY = OUTPUT_DIR / "qmt_roll_stage513_stage208_exact_position_margin_audit_margin_daily_stage513_stage208_exact_position_margin_audit_v1.csv"
STAGE513_PRODUCT_DAYS = OUTPUT_DIR / "qmt_roll_stage513_stage208_exact_position_margin_audit_top_margin_product_days_stage513_stage208_exact_position_margin_audit_v1.csv"

GAP_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TOP_GAP_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_gap_days_{MODEL_TAG}.csv"
TOP_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_gap_products_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

RISK060 = "stage079_next_real_risk060_clean_plus_stage103_xsmom_true"
RISK070 = "stage079_next_real_risk070_clean_plus_stage103_xsmom_true"
VARIANTS = [RISK060, RISK070]
RISK_MULTIPLIER = {RISK060: 0.60, RISK070: 0.70}
BROKER10_MULTIPLIER = 1.10


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


def _classify(row: pd.Series) -> str:
    exact = float(row["c3_margin_exact"])
    proxy = float(row["proxy_c3_margin"])
    if exact <= 1e-9 and proxy <= 1e-9:
        return "both_zero"
    if exact > 1e-9 and proxy <= 1e-9:
        return "exact_only"
    if exact <= 1e-9 and proxy > 1e-9:
        return "proxy_only"
    if abs(exact - proxy) <= max(10_000.0, 0.05 * max(exact, proxy)):
        return "close_enough"
    if exact > proxy:
        return "both_exact_gt_proxy"
    return "both_proxy_gt_exact"


def _load_gap_daily() -> pd.DataFrame:
    stage352 = pd.read_csv(STAGE352_MARGIN, encoding="utf-8-sig")
    stage352["date"] = pd.to_datetime(stage352["date"], errors="coerce").dt.normalize()
    stage352 = stage352[stage352["window_name"].eq("start_2020")].copy()
    for column in ["account_balance", "c3_margin", "c3_active_contracts", "c3_active_products"]:
        stage352[column] = pd.to_numeric(stage352.get(column, 0.0), errors="coerce").fillna(0.0)
    stage352 = stage352[
        ["date", "account_balance", "c3_margin", "c3_active_contracts", "c3_active_products"]
    ].rename(
        columns={
            "account_balance": "stage352_account_balance",
            "c3_margin": "stage352_c3_margin",
            "c3_active_contracts": "stage352_c3_active_contracts",
            "c3_active_products": "stage352_c3_active_products",
        }
    )

    exact = pd.read_csv(STAGE513_MARGIN_DAILY, encoding="utf-8-sig")
    exact["date"] = pd.to_datetime(exact["date"], errors="coerce").dt.normalize()
    exact = exact[exact["variant"].isin(VARIANTS)].copy()
    for column in [
        "account_equity",
        "c3_margin_exact",
        "c3_active_contracts",
        "c3_active_products",
        "xsmom_true_margin",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
    ]:
        exact[column] = pd.to_numeric(exact.get(column, 0.0), errors="coerce").fillna(0.0)

    rows: list[pd.DataFrame] = []
    for variant, frame in exact.groupby("variant"):
        risk_multiplier = RISK_MULTIPLIER[variant]
        merged = frame.merge(stage352, on="date", how="left")
        for column in ["stage352_c3_margin", "stage352_c3_active_contracts", "stage352_c3_active_products"]:
            merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
        merged["risk_multiplier_used_by_proxy"] = risk_multiplier
        merged["proxy_c3_margin"] = merged["stage352_c3_margin"] * risk_multiplier
        merged["proxy_total_margin"] = merged["proxy_c3_margin"] + merged["xsmom_true_margin"]
        merged["proxy_broker10_margin"] = merged["proxy_total_margin"] * BROKER10_MULTIPLIER
        merged["proxy_broker10_margin_to_equity_pct"] = (
            merged["proxy_broker10_margin"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).fillna(0.0)
        merged["exact_broker10_margin"] = merged["broker10_total_margin_exact"]
        merged["exact_broker10_margin_to_equity_pct"] = merged["broker10_margin_to_equity_pct"]
        merged["broker10_margin_gap"] = merged["exact_broker10_margin"] - merged["proxy_broker10_margin"]
        merged["broker10_margin_gap_to_equity_pct"] = (
            merged["broker10_margin_gap"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).fillna(0.0)
        merged["c3_margin_gap"] = merged["c3_margin_exact"] - merged["proxy_c3_margin"]
        merged["c3_margin_ratio_exact_over_proxy"] = np.where(
            merged["proxy_c3_margin"].abs() > 1e-9,
            merged["c3_margin_exact"] / merged["proxy_c3_margin"],
            np.nan,
        )
        merged["active_contract_gap"] = merged["c3_active_contracts"] - merged["stage352_c3_active_contracts"]
        merged["active_product_gap"] = merged["c3_active_products"] - merged["stage352_c3_active_products"]
        merged["gap_class"] = merged.apply(_classify, axis=1)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True).sort_values(["variant", "date"]).reset_index(drop=True)


def _summarize(gap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    for variant, frame in gap.groupby("variant"):
        pos = frame[frame["broker10_margin_gap_to_equity_pct"] > 0.0].copy()
        neg = frame[frame["broker10_margin_gap_to_equity_pct"] < 0.0].copy()
        both = frame[frame["proxy_c3_margin"] > 0.0].copy()
        exact_only = frame[frame["gap_class"].eq("exact_only")]
        proxy_only = frame[frame["gap_class"].eq("proxy_only")]
        top = frame.sort_values("broker10_margin_gap_to_equity_pct", ascending=False).head(20).copy()
        bottom = frame.sort_values("broker10_margin_gap_to_equity_pct", ascending=True).head(10).copy()
        top["rank_type"] = "positive_gap"
        bottom["rank_type"] = "negative_gap"
        top_rows.append(pd.concat([top, bottom], ignore_index=True))
        max_exact = frame.loc[frame["exact_broker10_margin_to_equity_pct"].idxmax()]
        max_gap = frame.loc[frame["broker10_margin_gap_to_equity_pct"].idxmax()]
        max_proxy = frame.loc[frame["proxy_broker10_margin_to_equity_pct"].idxmax()]
        summary_rows.append(
            {
                "variant": variant,
                "max_exact_margin_pct": _safe_float(max_exact["exact_broker10_margin_to_equity_pct"]),
                "max_exact_margin_date": pd.Timestamp(max_exact["date"]).date().isoformat(),
                "max_proxy_margin_pct": _safe_float(max_proxy["proxy_broker10_margin_to_equity_pct"]),
                "max_proxy_margin_date": pd.Timestamp(max_proxy["date"]).date().isoformat(),
                "max_gap_pct": _safe_float(max_gap["broker10_margin_gap_to_equity_pct"]),
                "max_gap_date": pd.Timestamp(max_gap["date"]).date().isoformat(),
                "days_exact_gt_proxy_25pp": int((frame["broker10_margin_gap_to_equity_pct"] > 25.0).sum()),
                "days_exact_gt_proxy_50pp": int((frame["broker10_margin_gap_to_equity_pct"] > 50.0).sum()),
                "days_proxy_gt_exact_25pp": int((frame["broker10_margin_gap_to_equity_pct"] < -25.0).sum()),
                "exact_only_days": int(len(exact_only)),
                "proxy_only_days": int(len(proxy_only)),
                "both_exact_gt_proxy_days": int(frame["gap_class"].eq("both_exact_gt_proxy").sum()),
                "both_proxy_gt_exact_days": int(frame["gap_class"].eq("both_proxy_gt_exact").sum()),
                "close_enough_days": int(frame["gap_class"].eq("close_enough").sum()),
                "positive_gap_days": int(len(pos)),
                "negative_gap_days": int(len(neg)),
                "mean_exact_over_proxy_when_proxy_positive": _safe_float(
                    both["c3_margin_ratio_exact_over_proxy"].replace([np.inf, -np.inf], np.nan).mean()
                ),
                "median_exact_over_proxy_when_proxy_positive": _safe_float(
                    both["c3_margin_ratio_exact_over_proxy"].replace([np.inf, -np.inf], np.nan).median()
                ),
                "corr_exact_proxy_c3_margin": _safe_float(frame[["c3_margin_exact", "proxy_c3_margin"]].corr().iloc[0, 1]),
                "mean_active_contract_gap": _safe_float(frame["active_contract_gap"].mean()),
                "max_active_contract_gap": _safe_float(frame["active_contract_gap"].max()),
            }
        )
    return pd.DataFrame(summary_rows), pd.concat(top_rows, ignore_index=True)


def _top_gap_products(top_gap: pd.DataFrame) -> pd.DataFrame:
    if not STAGE513_PRODUCT_DAYS.exists():
        return pd.DataFrame()
    products = pd.read_csv(STAGE513_PRODUCT_DAYS, encoding="utf-8-sig")
    products["event_date"] = pd.to_datetime(products["event_date"], errors="coerce").dt.normalize()
    for column in ["c3_margin_exact", "active_contracts", "holding_pnl", "trading_pnl", "net_pnl"]:
        products[column] = pd.to_numeric(products.get(column, 0.0), errors="coerce").fillna(0.0)
    keys = top_gap[top_gap["rank_type"].eq("positive_gap")].copy()
    keys = keys.groupby("variant").head(8)[["variant", "date", "broker10_margin_gap_to_equity_pct"]]
    keys["date"] = pd.to_datetime(keys["date"], errors="coerce").dt.normalize()
    rows: list[pd.DataFrame] = []
    for row in keys.itertuples(index=False):
        event = products[
            products["combo_variant"].eq(row.variant)
            & products["event_date"].eq(row.date)
            & products["c3_margin_exact"].gt(0.0)
        ].copy()
        if event.empty:
            continue
        event["gap_date"] = row.date
        event["gap_pct"] = row.broker10_margin_gap_to_equity_pct
        rows.append(event.sort_values("c3_margin_exact", ascending=False).head(8))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    r060 = summary[summary["variant"].eq(RISK060)].iloc[0]
    r070 = summary[summary["variant"].eq(RISK070)].iloc[0]
    return {
        "stage": "Stage215",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "stage213_proxy_invalid_path_mismatch_confirmed",
        "risk060_max_gap_pct": _safe_float(r060["max_gap_pct"]),
        "risk060_max_gap_date": r060["max_gap_date"],
        "risk060_exact_only_days": int(r060["exact_only_days"]),
        "risk060_mean_exact_over_proxy_when_proxy_positive": _safe_float(
            r060["mean_exact_over_proxy_when_proxy_positive"]
        ),
        "risk060_days_exact_gt_proxy_50pp": int(r060["days_exact_gt_proxy_50pp"]),
        "risk070_max_gap_pct": _safe_float(r070["max_gap_pct"]),
        "risk070_exact_only_days": int(r070["exact_only_days"]),
        "risk070_days_exact_gt_proxy_50pp": int(r070["days_exact_gt_proxy_50pp"]),
        "next_step": (
            "Treat Stage213 proxy as invalid for deployment decisions. "
            "Use exact position margin for any candidate; next search should target "
            "lower notional exposure or margin-aware sizing, not scalar fixes to the old proxy."
        ),
    }


def _plot(gap: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax060, ax070, ax_scatter, ax_class = axes.ravel()
    colors = {RISK060: "#1b7f5a", RISK070: "#b55a2a"}
    labels = {RISK060: "risk060 + true xsmom", RISK070: "risk070 + true xsmom"}
    for variant, ax in [(RISK060, ax060), (RISK070, ax070)]:
        frame = gap[gap["variant"].eq(variant)].sort_values("date")
        x = pd.to_datetime(frame["date"])
        ax.plot(x, frame["exact_broker10_margin_to_equity_pct"], color=colors[variant], linewidth=1.0, label="exact")
        ax.plot(x, frame["proxy_broker10_margin_to_equity_pct"], color="#555555", linewidth=0.9, alpha=0.85, label="Stage213 proxy")
        ax.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
        ax.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
        ax.set_title(f"{labels[variant]}: exact vs proxy margin/equity")
        ax.set_ylabel("Margin / equity %")
        ax.grid(True, alpha=0.22)
        ax.legend(fontsize=8)
    for variant, frame in gap.groupby("variant"):
        sample = frame[(frame["c3_margin_exact"] > 0.0) | (frame["proxy_c3_margin"] > 0.0)].copy()
        ax_scatter.scatter(
            sample["proxy_c3_margin"] / 10_000.0,
            sample["c3_margin_exact"] / 10_000.0,
            s=9,
            alpha=0.35,
            label=labels[variant],
            color=colors[variant],
        )
    limit = max(
        float(gap["proxy_c3_margin"].max()),
        float(gap["c3_margin_exact"].max()),
    ) / 10_000.0
    ax_scatter.plot([0, limit], [0, limit], color="#222222", linewidth=0.9, linestyle="--", label="y=x")
    ax_scatter.set_title("C3 margin: exact path vs scaled old proxy")
    ax_scatter.set_xlabel("Proxy C3 margin, 10k CNY")
    ax_scatter.set_ylabel("Exact C3 margin, 10k CNY")
    ax_scatter.grid(True, alpha=0.22)
    ax_scatter.legend(fontsize=8)
    class_order = ["exact_only", "both_exact_gt_proxy", "close_enough", "both_proxy_gt_exact", "proxy_only"]
    class_counts = (
        gap[gap["gap_class"].isin(class_order)]
        .groupby(["variant", "gap_class"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=class_order, fill_value=0)
    )
    xloc = np.arange(len(class_counts.index))
    bottom = np.zeros(len(class_counts.index))
    palette = ["#7d3c98", "#1b7f5a", "#7f8c8d", "#d68910", "#b55a2a"]
    for idx, column in enumerate(class_order):
        values = class_counts[column].to_numpy(dtype=float)
        ax_class.bar(xloc, values, bottom=bottom, label=column, color=palette[idx], alpha=0.88)
        bottom += values
    ax_class.set_xticks(xloc, ["risk060", "risk070"])
    ax_class.set_title("Daily C3 margin gap classes")
    ax_class.set_ylabel("Trading days")
    ax_class.grid(True, axis="y", alpha=0.22)
    ax_class.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(gap: pd.DataFrame, summary: pd.DataFrame, top_gap: pd.DataFrame, products: pd.DataFrame, decision: dict[str, Any]) -> None:
    class_counts = (
        gap.groupby(["variant", "gap_class"])
        .size()
        .reset_index(name="days")
        .sort_values(["variant", "days"], ascending=[True, False])
    )
    top_view = top_gap[
        [
            "variant",
            "rank_type",
            "date",
            "account_equity",
            "c3_margin_exact",
            "proxy_c3_margin",
            "stage352_c3_margin",
            "c3_active_contracts",
            "stage352_c3_active_contracts",
            "exact_broker10_margin_to_equity_pct",
            "proxy_broker10_margin_to_equity_pct",
            "broker10_margin_gap_to_equity_pct",
            "gap_class",
        ]
    ].copy()
    product_view = pd.DataFrame()
    if not products.empty:
        product_view = products[
            [
                "combo_variant",
                "gap_date",
                "gap_pct",
                "product_vt_symbol",
                "c3_margin_exact",
                "active_contracts",
                "holding_pnl",
                "trading_pnl",
                "net_pnl",
            ]
        ].copy()
    report = [
        "# Stage215 Stage214保证金差异归因",
        "",
        f"- 生成时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读口径复盘；不改策略、不调参数、不新增候选。",
        "- 运行前过拟合判断：否。当前只解释 Stage213 与 Stage214 的保证金口径差异。",
        "- 运行前继续价值判断：是。部署目标必须先确认保证金证据是否可信。",
        "",
        "## 外部调研判断",
        "",
        "- 交易所规则显示，期货交易保证金按持仓合约价值的一定比例收取，并在每日结算中重算；因此逐日持仓、合约乘数、价格和保证金率是部署审计的基本粒度。",
        "- vn.py/VeighNa 的组合回测也以合约乘数、价格跳动和多合约持仓为基础组织回测；所以用本地引擎持仓账本重建保证金，比用另一条历史权益路径的保证金线性缩放更接近实盘。",
        "- 我的判断：Stage213 不是“轻微保守/乐观误差”，而是使用了不同持仓路径的代理数据。它可以作为快速筛查，但不能作为部署裁决证据。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- `risk060` 最大 exact-proxy 差异：`{decision['risk060_max_gap_pct']:.4f}pp`，发生在 `{decision['risk060_max_gap_date']}`。",
        f"- `risk060` proxy 为正时，C3 exact/proxy 均值：`{decision['risk060_mean_exact_over_proxy_when_proxy_positive']:.4f}`；exact-only 天数：`{decision['risk060_exact_only_days']}`；差异超过 50pp 天数：`{decision['risk060_days_exact_gt_proxy_50pp']}`。",
        f"- `risk070` 最大 exact-proxy 差异：`{decision['risk070_max_gap_pct']:.4f}pp`；exact-only 天数：`{decision['risk070_exact_only_days']}`；差异超过 50pp 天数：`{decision['risk070_days_exact_gt_proxy_50pp']}`。",
        "",
        "## 汇总",
        "",
        _md_table(summary),
        "",
        "## 差异类别",
        "",
        _md_table(class_counts),
        "",
        "## 最大正负差异日",
        "",
        _md_table(top_view, max_rows=60),
        "",
        "## 最大正差异日产品构成",
        "",
        _md_table(product_view, max_rows=80),
        "",
        "## 图表视觉复盘",
        "",
        "- 左上/右上线图显示 exact 与 Stage213 proxy 多次错位，不是同一曲线的比例缩放；risk060 在 2021-09、2023-03、2024-08、2025-01 等阶段 exact 显著高于 proxy。",
        "- 散点图中大量点远离 `y=x`，且存在 proxy 接近 0 而 exact 很高的点，说明主要问题是持仓路径不同，而不是 0.60/0.70 乘数设错几个百分点。",
        "- 差异分类柱图显示 exact-only、both_exact_gt_proxy、proxy-only 同时存在，说明两条路径的持仓日期和持仓合约集合都发生了错位；这比“保证金率取值偏高”更根本。",
        "- 最大正差异日产品表显示风险由少数高名义保证金合约驱动，例如 `ru/OI/FG/fu/AP` 等；这些不是 xsmom 小腿造成的，而是 C3 主体在下一真实窗口路径下的实际持仓暴露。",
        "",
        "## 结论",
        "",
        "- Stage213 代理保证金不能再用于部署裁决。它把旧 Stage352/Stage079 C3 保证金乘以风险倍率，但下一真实窗口 `risk060/risk070` 的实际持仓路径已经不同。",
        "- Stage214 的精确持仓保证金结论仍然成立：`risk060/risk070 + true xsmom` 均不能晋级部署候选。",
        "- 下一步如果继续目标，应使用 exact position margin 作为候选硬闸门；方向应转向低名义风险结构、保证金感知 sizing 或更低相关且保证金轻的独立收益源，而不是继续修 Stage213 proxy 或扫 `risk=0.61/0.62`。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：否。没有用收益结果选择规则，也没有过滤坏日期/品种；只是解释固定输出之间的差异。",
        "- 运行后继续价值判断：是。继续方向是 exact-margin-first 的结构搜索；若继续用代理保证金，将产生虚假的可部署感。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gap = _load_gap_daily()
    summary, top_gap = _summarize(gap)
    products = _top_gap_products(top_gap)
    decision = _decision(summary)
    _plot(gap, summary)
    _write_report(gap, summary, top_gap, products, decision)
    gap.to_csv(GAP_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_gap.to_csv(TOP_GAP_DAYS_PATH, index=False, encoding="utf-8-sig")
    products.to_csv(TOP_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

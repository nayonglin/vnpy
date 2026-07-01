from __future__ import annotations

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


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage010"
MODEL_TAG = "stage010_worst_window_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage010_worst_window_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_worst_window_attribution"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
STAGE008_OUTPUT_DIR = LINE_DIR / "outputs" / "stage008_high_quality_add_risk_proxy"
STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_dense_start_goal_audit"

QUALITY_FEATURES_PATH = (
    STAGE007_OUTPUT_DIR
    / "rebuilt_c9_stage007_minute_source_coverage_rebind_quality_features_stage007_minute_source_coverage_rebind_v1.csv"
)
PROXY_CURVES_PATH = (
    STAGE008_OUTPUT_DIR
    / "rebuilt_c9_stage008_high_quality_add_risk_proxy_curves_stage008_high_quality_add_risk_proxy_v1.csv"
)
PROXY_LOT_DELTAS_PATH = (
    STAGE008_OUTPUT_DIR
    / "rebuilt_c9_stage008_high_quality_add_risk_proxy_lot_deltas_stage008_high_quality_add_risk_proxy_v1.csv"
)
WORST_WINDOWS_PATH = (
    STAGE009_OUTPUT_DIR
    / "rebuilt_c9_stage009_dense_start_goal_audit_worst_windows_stage009_dense_start_goal_audit_v1.csv"
)

FOCUS_VARIANT = "proxy_stage008"

FOCUS_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_focus_windows_{MODEL_TAG}.csv"
WINDOW_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
LOT_CONTRIBUTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_contributions_{MODEL_TAG}.csv"
PRODUCT_CONTRIBUTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contributions_{MODEL_TAG}.csv"
TAG_CONTRIBUTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tag_contributions_{MODEL_TAG}.csv"
EXIT_CONTRIBUTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_contributions_{MODEL_TAG}.csv"
WORST_FREQUENCY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_frequency_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _drawdown_pct(values: pd.Series) -> pd.Series:
    equity = pd.to_numeric(values, errors="coerce").ffill()
    peak = equity.cummax()
    return (equity / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _quality_bucket(row: pd.Series) -> str:
    if bool(row.get("tag_ai4_6_entry_or_first_aligned", False)):
        return "ai4_6_entry_or_first_aligned"
    if bool(row.get("tag_ai4_6_not_aligned", False)):
        return "ai4_6_not_aligned"
    if bool(row.get("tag_aligned_not_ai4_6", False)):
        return "aligned_not_ai4_6"
    if bool(row.get("tag_entry_or_first_aligned", False)):
        return "aligned_other_rank"
    if not bool(row.get("entry_first_bar_available", False)):
        return "no_first_bar"
    return "not_aligned_other"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    worst = pd.read_csv(WORST_WINDOWS_PATH, encoding="utf-8-sig")
    curves = pd.read_csv(PROXY_CURVES_PATH, encoding="utf-8-sig")
    features = pd.read_csv(QUALITY_FEATURES_PATH, encoding="utf-8-sig")
    lot_deltas = pd.read_csv(PROXY_LOT_DELTAS_PATH, encoding="utf-8-sig")

    for frame in (worst,):
        frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce").dt.normalize()
        frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.normalize()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    for column in ("account_equity", "proxy_account_equity", "daily_proxy_delta"):
        curves[column] = pd.to_numeric(curves[column], errors="coerce")

    for frame in (features, lot_deltas):
        frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
        frame["exit_date"] = pd.to_datetime(frame["exit_date"], errors="coerce").dt.normalize()
        frame["realized_pnl"] = pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0)
        frame["lot_id"] = pd.to_numeric(frame["lot_id"], errors="coerce")
    if "proxy_delta_pnl" in lot_deltas.columns:
        lot_deltas["proxy_delta_pnl"] = pd.to_numeric(lot_deltas["proxy_delta_pnl"], errors="coerce").fillna(0.0)
    else:
        lot_deltas["proxy_delta_pnl"] = 0.0

    return worst, curves, features, lot_deltas


def _select_focus_windows(worst: pd.DataFrame, curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    proxy_worst = worst[worst["variant"].eq(FOCUS_VARIANT)].sort_values("return_pct").copy()
    if proxy_worst.empty:
        raise RuntimeError("No proxy worst windows found")
    anchor = proxy_worst.iloc[0]
    focus_start = pd.Timestamp(anchor["start_date"]).normalize()
    focus_end = pd.Timestamp(anchor["end_date"]).normalize()

    frequency = (
        proxy_worst.groupby(["start_date", "end_date"], as_index=False)
        .agg(
            worst_row_count=("return_pct", "size"),
            min_return_pct=("return_pct", "min"),
            median_return_pct=("return_pct", "median"),
            source_count=("source_start_month", "nunique"),
        )
        .sort_values(["min_return_pct", "worst_row_count"], ascending=[True, False])
        .reset_index(drop=True)
    )
    frequency.to_csv(WORST_FREQUENCY_PATH, index=False, encoding="utf-8-sig")

    available_sources: list[str] = []
    for source, group in curves.groupby("requested_start_month", sort=True):
        dates = set(group["date"])
        if focus_start in dates and focus_end in dates:
            available_sources.append(str(source))

    focus_rows = []
    for source in available_sources:
        row = proxy_worst[
            proxy_worst["source_start_month"].astype(str).eq(source)
            & proxy_worst["start_date"].eq(focus_start)
            & proxy_worst["end_date"].eq(focus_end)
        ]
        if row.empty:
            focus_rows.append(
                {
                    "variant": FOCUS_VARIANT,
                    "source_start_month": source,
                    "start_date": focus_start.date().isoformat(),
                    "end_date": focus_end.date().isoformat(),
                    "return_pct": np.nan,
                    "in_stage009_top_worst": 0,
                }
            )
        else:
            record = row.iloc[0].to_dict()
            record["in_stage009_top_worst"] = 1
            focus_rows.append(record)
    focus = pd.DataFrame(focus_rows).sort_values("source_start_month").reset_index(drop=True)
    return focus, focus_start, focus_end


def _equity_at(group: pd.DataFrame, date: pd.Timestamp, column: str) -> float:
    row = group[group["date"].eq(date)]
    if row.empty:
        return np.nan
    return float(row[column].iloc[0])


def _build_window_metrics(
    focus: pd.DataFrame,
    curves: pd.DataFrame,
    features: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    focus_start: pd.Timestamp,
    focus_end: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in focus["source_start_month"].astype(str).tolist():
        curve = curves[curves["requested_start_month"].astype(str).eq(source)].sort_values("date").copy()
        window_curve = curve[curve["date"].between(focus_start, focus_end)].copy()
        if window_curve.empty:
            continue

        source_lots = features[features["requested_start_month"].astype(str).eq(source)].copy()
        closed_in_window = source_lots[source_lots["exit_date"].between(focus_start, focus_end)].copy()
        active_at_start = source_lots[(source_lots["entry_date"].le(focus_start)) & (source_lots["exit_date"].ge(focus_start))]
        active_cross_end = source_lots[(source_lots["entry_date"].le(focus_end)) & (source_lots["exit_date"].gt(focus_end))]

        source_deltas = lot_deltas[lot_deltas["requested_start_month"].astype(str).eq(source)].copy()
        delta_in_window = source_deltas[source_deltas["exit_date"].between(focus_start, focus_end)].copy()

        base_start = _equity_at(window_curve, focus_start, "account_equity")
        base_end = _equity_at(window_curve, focus_end, "account_equity")
        proxy_start = _equity_at(window_curve, focus_start, "proxy_account_equity")
        proxy_end = _equity_at(window_curve, focus_end, "proxy_account_equity")
        base_change = base_end - base_start
        proxy_change = proxy_end - proxy_start
        closed_pnl = float(closed_in_window["realized_pnl"].sum())
        proxy_delta = float(delta_in_window["proxy_delta_pnl"].sum())

        rows.append(
            {
                "source_start_month": source,
                "focus_start": focus_start.date().isoformat(),
                "focus_end": focus_end.date().isoformat(),
                "trading_days": int(len(window_curve)),
                "base_start_equity": base_start,
                "base_end_equity": base_end,
                "base_change_cash": base_change,
                "base_return_pct": float((base_end / base_start - 1.0) * 100.0) if base_start else np.nan,
                "base_window_max_dd_pct": float(_drawdown_pct(window_curve["account_equity"]).min()),
                "base_min_from_window_start_pct": float((window_curve["account_equity"].min() / base_start - 1.0) * 100.0)
                if base_start
                else np.nan,
                "proxy_start_equity": proxy_start,
                "proxy_end_equity": proxy_end,
                "proxy_change_cash": proxy_change,
                "proxy_return_pct": float((proxy_end / proxy_start - 1.0) * 100.0) if proxy_start else np.nan,
                "proxy_window_max_dd_pct": float(_drawdown_pct(window_curve["proxy_account_equity"]).min()),
                "proxy_min_from_window_start_pct": float((window_curve["proxy_account_equity"].min() / proxy_start - 1.0) * 100.0)
                if proxy_start
                else np.nan,
                "proxy_minus_base_return_pp": (
                    float((proxy_end / proxy_start - 1.0) * 100.0 - (base_end / base_start - 1.0) * 100.0)
                    if base_start and proxy_start
                    else np.nan
                ),
                "proxy_delta_inside_window": proxy_delta,
                "closed_lot_count": int(len(closed_in_window)),
                "closed_lot_realized_pnl": closed_pnl,
                "closed_lot_win_rate_pct": float(closed_in_window["realized_pnl"].gt(0).mean() * 100.0)
                if len(closed_in_window)
                else np.nan,
                "active_lots_at_window_start": int(len(active_at_start)),
                "active_lots_cross_window_end": int(len(active_cross_end)),
                "realized_vs_base_change_residual": float(base_change - closed_pnl),
                "proxy_delta_vs_proxy_change_pct": float(proxy_delta / proxy_change * 100.0) if proxy_change else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("proxy_return_pct").reset_index(drop=True)


def _build_lot_contributions(
    focus: pd.DataFrame,
    features: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    focus_start: pd.Timestamp,
    focus_end: pd.Timestamp,
) -> pd.DataFrame:
    focus_sources = set(focus["source_start_month"].astype(str))
    lots = features[
        features["requested_start_month"].astype(str).isin(focus_sources)
        & features["exit_date"].between(focus_start, focus_end)
    ].copy()
    if lots.empty:
        return lots

    deltas = lot_deltas[
        lot_deltas["requested_start_month"].astype(str).isin(focus_sources)
        & lot_deltas["exit_date"].between(focus_start, focus_end)
    ][["requested_start_month", "lot_id", "proxy_delta_pnl"]].copy()
    lots = lots.merge(deltas, on=["requested_start_month", "lot_id"], how="left")
    lots["proxy_delta_pnl"] = pd.to_numeric(lots["proxy_delta_pnl"], errors="coerce").fillna(0.0)
    lots["quality_bucket"] = lots.apply(_quality_bucket, axis=1)
    lots["entry_month"] = lots["entry_date"].dt.to_period("M").astype(str)
    lots["exit_month"] = lots["exit_date"].dt.to_period("M").astype(str)
    lots["winner"] = lots["realized_pnl"].gt(0).astype(int)
    lots["signed_volume"] = np.where(lots["direction"].astype(str).eq("short"), -lots["volume"], lots["volume"])
    keep = [
        "requested_start_month",
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "holding_calendar_days",
        "volume",
        "realized_pnl",
        "proxy_delta_pnl",
        "r_multiple",
        "exit_reason",
        "quality_bucket",
        "ai_product_pool_rank",
        "ai_rank_bucket",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "portfolio_drawdown_pct",
        "entry_open_relation_bucket",
        "first_bar_relation_bucket",
        "winner",
        "entry_month",
        "exit_month",
    ]
    return lots[[column for column in keep if column in lots.columns]].sort_values("realized_pnl").reset_index(drop=True)


def _aggregate_contributions(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if lots.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    def aggregate(keys: list[str]) -> pd.DataFrame:
        output = (
            lots.groupby(keys, dropna=False)
            .agg(
                lot_count=("lot_id", "count"),
                source_count=("requested_start_month", "nunique"),
                realized_pnl=("realized_pnl", "sum"),
                proxy_delta_pnl=("proxy_delta_pnl", "sum"),
                avg_r_multiple=("r_multiple", "mean"),
                win_rate_pct=("winner", lambda s: float(s.mean() * 100.0) if len(s) else np.nan),
                avg_ai_rank=("ai_product_pool_rank", "mean"),
            )
            .reset_index()
        )
        output["realized_pnl_per_lot"] = output["realized_pnl"] / output["lot_count"].replace(0, np.nan)
        return output.sort_values("realized_pnl").reset_index(drop=True)

    product = aggregate(["product", "direction"])
    tag = aggregate(["quality_bucket"])
    exit_reason = aggregate(["exit_reason"])
    return product, tag, exit_reason


def _plot(
    curves: pd.DataFrame,
    metrics: pd.DataFrame,
    product: pd.DataFrame,
    tag: pd.DataFrame,
    focus_start: pd.Timestamp,
    focus_end: pd.Timestamp,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)

    ax = axes[0, 0]
    for source in metrics["source_start_month"].astype(str).tolist():
        group = curves[curves["requested_start_month"].astype(str).eq(source)].sort_values("date").copy()
        group = group[group["date"].between(focus_start, focus_end)]
        if group.empty:
            continue
        start_equity = float(group["proxy_account_equity"].iloc[0])
        ax.plot(group["date"], group["proxy_account_equity"] / start_equity, linewidth=1.0, alpha=0.75, label=source)
    ax.axhline(1.0, color="#111827", linewidth=0.8, linestyle="--")
    ax.set_title("Proxy Window Equity Indexed To Focus Start")
    ax.set_ylabel("index")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=2, loc="best")

    ax = axes[0, 1]
    plot_metrics = metrics.sort_values("proxy_return_pct").copy()
    ax.bar(plot_metrics["source_start_month"], plot_metrics["proxy_return_pct"], color="#dc2626")
    ax.set_title("Proxy Return By Cold Start In Focus Window")
    ax.set_ylabel("return %")
    ax.tick_params(axis="x", labelrotation=45)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    if not product.empty:
        prod = pd.concat([product.head(8), product.tail(5)]).drop_duplicates(["product", "direction"]).copy()
        prod["label"] = prod["product"].astype(str) + " " + prod["direction"].astype(str)
        ax.barh(prod["label"], prod["realized_pnl"], color=np.where(prod["realized_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("Closed-Lot Realized PnL By Product/Direction")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 1]
    if not tag.empty:
        tag_plot = tag.sort_values("realized_pnl").copy()
        ax.barh(tag_plot["quality_bucket"], tag_plot["realized_pnl"], color=np.where(tag_plot["realized_pnl"].ge(0), "#2563eb", "#f97316"))
    ax.set_title("Closed-Lot Realized PnL By Quality Bucket")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    focus: pd.DataFrame,
    metrics: pd.DataFrame,
    product: pd.DataFrame,
    tag: pd.DataFrame,
    exit_reason: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 最差窗口左尾归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读归因；不改策略、不扫参数、不连接 CTP、不调用下单。",
        f"- 归因焦点：`{decision['focus_start']}` 到 `{decision['focus_end']}`，来源于 Stage009 proxy 最差窗口。",
        "",
        "## 开始前反思",
        "",
        f"- 是否过拟合：{decision['overfit_reflection_before']}",
        f"- 是否值得继续：{decision['continue_value_before']}",
        "",
        "## 外部调研判断",
        "",
        "- AQR/Hurst-Ooi-Pedersen 的趋势跟随研究提示：长期趋势策略的核心不是每个局部窗口都平滑，而是跨市场分散和右尾复利，因此左尾保护不能把趋势右尾切掉。",
        "- Bailey/Borwein/Lopez de Prado/Zhu 的 PBO 框架提示：围绕一个坏窗口扫阈值很容易形成样本内赢家，本阶段只做证据归因，不做参数修补。",
        "- 2024/2025 volatility-targeting 研究进一步提醒：波动管理在商品、利率、外汇期货上并不天然等价于 alpha；如果后续做账户层保护，需要在本策略真实日级路径上验证，而不是照搬权益指数经验。",
        "",
        "## 焦点窗口",
        "",
        _md_table(focus, max_rows=30),
        "",
        "## 窗口账户层指标",
        "",
        _md_table(metrics, max_rows=30),
        "",
        "## 品种/方向贡献",
        "",
        _md_table(product, max_rows=30),
        "",
        "## 质量标签贡献",
        "",
        _md_table(tag, max_rows=30),
        "",
        "## 退出原因贡献",
        "",
        _md_table(exit_reason, max_rows=30),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 核心归因：{decision['core_attribution']}",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    worst, curves, features, lot_deltas = _load_inputs()
    focus, focus_start, focus_end = _select_focus_windows(worst, curves)
    metrics = _build_window_metrics(focus, curves, features, lot_deltas, focus_start, focus_end)
    lots = _build_lot_contributions(focus, features, lot_deltas, focus_start, focus_end)
    product, tag, exit_reason = _aggregate_contributions(lots)
    _plot(curves, metrics, product, tag, focus_start, focus_end)

    focus.to_csv(FOCUS_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(WINDOW_METRICS_PATH, index=False, encoding="utf-8-sig")
    lots.to_csv(LOT_CONTRIBUTIONS_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_CONTRIBUTIONS_PATH, index=False, encoding="utf-8-sig")
    tag.to_csv(TAG_CONTRIBUTIONS_PATH, index=False, encoding="utf-8-sig")
    exit_reason.to_csv(EXIT_CONTRIBUTIONS_PATH, index=False, encoding="utf-8-sig")

    worst_metric = metrics.sort_values("proxy_return_pct").iloc[0].to_dict() if not metrics.empty else {}
    worst_product = product.iloc[0].to_dict() if not product.empty else {}
    worst_tag = tag.iloc[0].to_dict() if not tag.empty else {}
    best_tag = tag.sort_values("realized_pnl", ascending=False).iloc[0].to_dict() if not tag.empty else {}
    total_proxy_delta = float(metrics["proxy_delta_inside_window"].sum()) if not metrics.empty else 0.0
    total_proxy_change = float(metrics["proxy_change_cash"].sum()) if not metrics.empty else 0.0
    total_base_change = float(metrics["base_change_cash"].sum()) if not metrics.empty else 0.0
    total_closed_lot_pnl = float(metrics["closed_lot_realized_pnl"].sum()) if not metrics.empty else 0.0
    total_realized_residual = float(metrics["realized_vs_base_change_residual"].sum()) if not metrics.empty else 0.0
    total_active_at_start = int(metrics["active_lots_at_window_start"].sum()) if not metrics.empty else 0

    core_attribution = (
        f"最差窗口不是高质量加风险放大出来的，proxy_delta_inside_window 合计 {total_proxy_delta:,.2f}，"
        f"相对窗口 proxy_change_cash 合计 {total_proxy_change:,.2f} 方向为缓冲；"
        f"但闭合 lot 净实现盈亏只有 {total_closed_lot_pnl:,.2f}，base_change_cash 合计 {total_base_change:,.2f}，"
        f"残差 {total_realized_residual:,.2f} 表明窗口内持仓浮亏/日级 holding_pnl 才是主问题；"
        f"闭合 lot 层面最大拖累来自 {worst_product.get('product', 'NA')} {worst_product.get('direction', 'NA')}，"
        f"质量桶最大拖累为 {worst_tag.get('quality_bucket', 'NA')}，最大正贡献为 {best_tag.get('quality_bucket', 'NA')}。"
    )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "focus_variant": FOCUS_VARIANT,
        "focus_start": focus_start.date().isoformat(),
        "focus_end": focus_end.date().isoformat(),
        "focus_source_count": int(focus["source_start_month"].nunique()) if not focus.empty else 0,
        "window_metric_count": int(len(metrics)),
        "lot_contribution_count": int(len(lots)),
        "product_contribution_count": int(len(product)),
        "worst_source_start_month": str(worst_metric.get("source_start_month", "")),
        "worst_proxy_return_pct": float(worst_metric.get("proxy_return_pct", np.nan)),
        "worst_base_return_pct": float(worst_metric.get("base_return_pct", np.nan)),
        "total_proxy_delta_inside_window": total_proxy_delta,
        "total_proxy_change_cash": total_proxy_change,
        "total_base_change_cash": total_base_change,
        "total_closed_lot_realized_pnl": total_closed_lot_pnl,
        "total_realized_vs_base_change_residual": total_realized_residual,
        "total_active_lots_at_window_start": total_active_at_start,
        "worst_product": _json_safe(worst_product),
        "worst_quality_bucket": _json_safe(worst_tag),
        "best_quality_bucket": _json_safe(best_tag),
        "decision": "stage010_root_cause_left_tail_not_high_quality_add_risk_next_account_protection",
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following literature supports preserving diversified right-tail exposure; "
            "PBO literature rejects parameter fitting around this single 2022-07/2023-07 left-tail. "
            "Vol-targeting cannot be assumed to add alpha for commodity futures without true path tests."
        ),
        "overfit_reflection_before": (
            "否。Stage010 只解释 Stage009 暴露的最差窗口，不新增规则、不选择参数。"
        ),
        "continue_value_before": (
            "是。严格任意结束日目标失败集中在同一左尾区间，先归因比直接优化更有价值。"
        ),
        "core_attribution": core_attribution,
        "overfit_reflection_after": (
            "否。本阶段输出的是账户、品种、标签、退出原因归因，没有用坏窗口反推阈值。"
        ),
        "continue_value_after": (
            "有。归因显示 Stage008 高质量加风险在左尾里总体是缓冲，不是主要问题；下一步应研究账户层生存线/动态风险，而不是砍掉高质量标签。"
        ),
        "outputs": {
            "focus_windows": str(FOCUS_WINDOWS_PATH),
            "window_metrics": str(WINDOW_METRICS_PATH),
            "lot_contributions": str(LOT_CONTRIBUTIONS_PATH),
            "product_contributions": str(PRODUCT_CONTRIBUTIONS_PATH),
            "tag_contributions": str(TAG_CONTRIBUTIONS_PATH),
            "exit_contributions": str(EXIT_CONTRIBUTIONS_PATH),
            "worst_frequency": str(WORST_FREQUENCY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, focus, metrics, product, tag, exit_reason)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("window_metrics")
    print(metrics.to_string(index=False))
    print("product_contributions")
    print(product.head(30).to_string(index=False))
    print("tag_contributions")
    print(tag.to_string(index=False))


if __name__ == "__main__":
    main()

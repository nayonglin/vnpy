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
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage011"
MODEL_TAG = "stage011_stage010_remaining_left_tail_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution"

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_meta_label_entry_quality_audit as s009


LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage011_stage010_remaining_left_tail_attribution"

STAGE010_OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_quality_add_risk_proxy"
STAGE010_PREFIX = "rebuilt_c9_v2_stage010_quality_add_risk_proxy"
STAGE010_TAG = "stage010_quality_add_risk_proxy_v1"
STAGE010_CURVES_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_curves_{STAGE010_TAG}.csv"
STAGE010_LOT_DELTAS_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_lot_deltas_{STAGE010_TAG}.csv.gz"
STAGE010_WORST_WINDOWS_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_goal_worst_windows_{STAGE010_TAG}.csv"
STAGE010_DECISION_PATH = STAGE010_OUTPUT_DIR / f"{STAGE010_PREFIX}_decision_{STAGE010_TAG}.json"

STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
STAGE009_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"
STAGE009_TAG = "stage009_meta_label_entry_quality_audit_v1"
STAGE009_EVENTS_PATH = STAGE009_OUTPUT_DIR / f"{STAGE009_PREFIX}_quality_events_{STAGE009_TAG}.csv.gz"

FOCUS_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_focus_windows_{MODEL_TAG}.csv"
WINDOW_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_attribution_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0433_stage011_stage010_remaining_left_tail_attribution.md"

TARGET_VARIANT = "stage010_quality_add_risk_proxy"
TOP_N_FOCUS_WINDOWS = 64


def _json_safe(value: Any) -> Any:
    return s009._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009._md_table(frame, max_rows=max_rows or 20)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def select_focus_windows(worst_windows: pd.DataFrame, top_n: int = TOP_N_FOCUS_WINDOWS) -> pd.DataFrame:
    data = worst_windows.copy()
    data["variant"] = data["variant"].astype(str)
    data["return_pct"] = pd.to_numeric(data["return_pct"], errors="coerce")
    data = data[data["variant"].eq(TARGET_VARIANT) & data["return_pct"].lt(0.0)].copy()
    if data.empty:
        return data
    for column in ["start_date", "end_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    data["source_start_month"] = data["source_start_month"].astype(str)
    data = data.dropna(subset=["start_date", "end_date"]).sort_values("return_pct", ascending=True)
    keys = ["source_start_month", "start_date", "end_date"]
    return data.drop_duplicates(keys).head(top_n).reset_index(drop=True)


def _curve_at(curves: pd.DataFrame, source: str, date: pd.Timestamp) -> pd.Series:
    row = curves[curves["requested_start_month"].astype(str).eq(source) & curves["date"].eq(date)]
    if row.empty:
        raise ValueError(f"missing curve row source={source} date={date.date().isoformat()}")
    return row.iloc[0]


def _in_window(frame: pd.DataFrame, source: str, date_column: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.iloc[0:0].copy()
    data = frame.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce").dt.normalize()
    return data[
        data["requested_start_month"].eq(source)
        & data[date_column].gt(start)
        & data[date_column].le(end)
    ].copy()


def attribute_focus_window(
    window: pd.Series,
    curves: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    quality_events: pd.DataFrame,
) -> dict[str, Any]:
    curves = curves.copy()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    source = str(window["source_start_month"])
    start = _date(window["start_date"])
    end = _date(window["end_date"])
    start_row = _curve_at(curves, source, start)
    end_row = _curve_at(curves, source, end)
    base_start = float(start_row["account_equity"])
    base_end = float(end_row["account_equity"])
    stage010_start = float(start_row["stage010_account_equity"])
    stage010_end = float(end_row["stage010_account_equity"])
    proxy_start = float(start_row.get("stage010_cum_delta", 0.0))
    proxy_end = float(end_row.get("stage010_cum_delta", 0.0))
    selected = _in_window(lot_deltas, source, "exit_date", start, end)
    events = _in_window(quality_events, source, "exit_date", start, end)
    if not events.empty and "stage010_selector" in events.columns:
        events = events.drop(columns=["stage010_selector"])
    selected_pnl = float(_numeric(selected, "realized_pnl", 0.0).sum()) if not selected.empty else 0.0
    selected_delta = float(_numeric(selected, "stage010_proxy_delta_pnl", 0.0).sum()) if not selected.empty else 0.0
    event_pnl = float(_numeric(events, "realized_pnl", 0.0).sum()) if not events.empty else 0.0
    selected_keys = set()
    if not selected.empty:
        for row in selected.to_dict("records"):
            selected_keys.add(
                (
                    str(row.get("requested_start_month")),
                    str(row.get("lot_id")),
                    str(row.get("open_trade_id")),
                    pd.Timestamp(row.get("exit_date")).normalize() if pd.notna(row.get("exit_date")) else pd.NaT,
                )
            )
    if not events.empty:
        event_keys = [
            (
                str(row.get("requested_start_month")),
                str(row.get("lot_id")),
                str(row.get("open_trade_id")),
                pd.Timestamp(row.get("exit_date")).normalize() if pd.notna(row.get("exit_date")) else pd.NaT,
            )
            for row in events.to_dict("records")
        ]
        events["_stage010_selected"] = [key in selected_keys for key in event_keys]
        unselected_pnl = float(_numeric(events[~events["_stage010_selected"]], "realized_pnl", 0.0).sum())
    else:
        unselected_pnl = 0.0
    base_delta = base_end - base_start
    stage010_delta = stage010_end - stage010_start
    proxy_delta = proxy_end - proxy_start
    return {
        "source_start_month": source,
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "return_pct": float(window.get("return_pct", np.nan)),
        "period_calendar_days": int(window.get("period_calendar_days", (end - start).days)),
        "period_trading_days": int(window.get("period_trading_days", np.nan)) if pd.notna(window.get("period_trading_days", np.nan)) else np.nan,
        "base_start_equity": base_start,
        "base_end_equity": base_end,
        "base_equity_delta": base_delta,
        "stage010_start_equity": stage010_start,
        "stage010_end_equity": stage010_end,
        "stage010_equity_delta": stage010_delta,
        "proxy_delta_in_window": proxy_delta,
        "proxy_delta_from_lots": selected_delta,
        "proxy_delta_abs_diff": abs(proxy_delta - selected_delta),
        "selected_lot_count": int(len(selected)),
        "selected_closed_lot_pnl": selected_pnl,
        "quality_event_count": int(len(events)),
        "quality_event_pnl": event_pnl,
        "unselected_quality_event_pnl": unselected_pnl,
        "base_delta_minus_quality_event_pnl": base_delta - event_pnl,
        "stage010_loss_abs": abs(stage010_delta) if stage010_delta < 0 else 0.0,
        "proxy_delta_to_stage010_loss_abs_pct": (
            proxy_delta / abs(stage010_delta) * 100.0 if stage010_delta < 0 and abs(stage010_delta) > 1e-12 else np.nan
        ),
        "selected_pnl_to_stage010_loss_abs_pct": (
            selected_pnl / abs(stage010_delta) * 100.0 if stage010_delta < 0 and abs(stage010_delta) > 1e-12 else np.nan
        ),
        "base_delta_minus_quality_event_pnl_to_loss_abs_pct": (
            (base_delta - event_pnl) / abs(stage010_delta) * 100.0
            if stage010_delta < 0 and abs(stage010_delta) > 1e-12
            else np.nan
        ),
    }


def build_window_attribution(
    focus_windows: pd.DataFrame,
    curves: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    quality_events: pd.DataFrame,
) -> pd.DataFrame:
    rows = [attribute_focus_window(row, curves, lot_deltas, quality_events) for _, row in focus_windows.iterrows()]
    return pd.DataFrame(rows)


def build_product_direction_attribution(
    focus_windows: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    quality_events: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for _, window in focus_windows.iterrows():
        source = str(window["source_start_month"])
        start = _date(window["start_date"])
        end = _date(window["end_date"])
        selected = _in_window(lot_deltas, source, "exit_date", start, end)
        events = _in_window(quality_events, source, "exit_date", start, end)
        if not selected.empty:
            selected = selected.copy()
            selected["focus_source_start_month"] = source
            selected["focus_start_date"] = start.date().isoformat()
            selected["focus_end_date"] = end.date().isoformat()
            selected["stage010_selected"] = True
            rows.append(selected)
        if not events.empty:
            selected_keys = set()
            if not selected.empty:
                selected_keys = {
                    (
                        str(row.get("requested_start_month")),
                        str(row.get("lot_id")),
                        str(row.get("open_trade_id")),
                        pd.Timestamp(row.get("exit_date")).normalize() if pd.notna(row.get("exit_date")) else pd.NaT,
                    )
                    for row in selected.to_dict("records")
                }
            unselected_records = []
            for row in events.to_dict("records"):
                key = (
                    str(row.get("requested_start_month")),
                    str(row.get("lot_id")),
                    str(row.get("open_trade_id")),
                    pd.Timestamp(row.get("exit_date")).normalize() if pd.notna(row.get("exit_date")) else pd.NaT,
                )
                if key not in selected_keys:
                    row["stage010_proxy_delta_pnl"] = 0.0
                    row["focus_source_start_month"] = source
                    row["focus_start_date"] = start.date().isoformat()
                    row["focus_end_date"] = end.date().isoformat()
                    row["stage010_selected"] = False
                    unselected_records.append(row)
            if unselected_records:
                rows.append(pd.DataFrame(unselected_records))
    if not rows:
        return pd.DataFrame()
    detail = pd.concat(rows, ignore_index=True, sort=False)
    for column in ["realized_pnl", "stage010_proxy_delta_pnl"]:
        detail[column] = pd.to_numeric(detail.get(column, 0.0), errors="coerce").fillna(0.0)
    detail["product"] = detail.get("product", "").astype(str)
    detail["direction"] = detail.get("direction", "").astype(str)
    grouped = (
        detail.groupby(["stage010_selected", "product", "direction"], dropna=False)
        .agg(
            duplicated_lot_rows=("realized_pnl", "size"),
            unique_lot_count=("lot_id", "nunique"),
            focus_window_count=("focus_start_date", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            proxy_delta_pnl=("stage010_proxy_delta_pnl", "sum"),
        )
        .reset_index()
        .sort_values(["stage010_selected", "realized_pnl"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return grouped


def build_source_summary(window_attribution: pd.DataFrame) -> pd.DataFrame:
    if window_attribution.empty:
        return pd.DataFrame()
    return (
        window_attribution.groupby("source_start_month", as_index=False)
        .agg(
            focus_window_count=("source_start_month", "size"),
            worst_return_pct=("return_pct", "min"),
            stage010_equity_delta_sum=("stage010_equity_delta", "sum"),
            base_equity_delta_sum=("base_equity_delta", "sum"),
            proxy_delta_sum=("proxy_delta_in_window", "sum"),
            selected_closed_lot_pnl_sum=("selected_closed_lot_pnl", "sum"),
            unselected_quality_event_pnl_sum=("unselected_quality_event_pnl", "sum"),
            base_delta_minus_quality_event_pnl_sum=("base_delta_minus_quality_event_pnl", "sum"),
        )
        .sort_values("worst_return_pct")
        .reset_index(drop=True)
    )


def make_decision(
    focus_windows: pd.DataFrame,
    window_attribution: pd.DataFrame,
    product_direction: pd.DataFrame,
) -> dict[str, Any]:
    total_loss_abs = float(pd.to_numeric(window_attribution.get("stage010_loss_abs"), errors="coerce").sum())
    proxy_delta = float(pd.to_numeric(window_attribution.get("proxy_delta_in_window"), errors="coerce").sum())
    selected_pnl = float(pd.to_numeric(window_attribution.get("selected_closed_lot_pnl"), errors="coerce").sum())
    unselected_pnl = float(pd.to_numeric(window_attribution.get("unselected_quality_event_pnl"), errors="coerce").sum())
    unexplained = float(pd.to_numeric(window_attribution.get("base_delta_minus_quality_event_pnl"), errors="coerce").sum())
    proxy_loss_share = proxy_delta / total_loss_abs * 100.0 if total_loss_abs > 0 else np.nan
    unexplained_loss_share = unexplained / total_loss_abs * 100.0 if total_loss_abs > 0 else np.nan
    selected_negative = (
        product_direction[
            product_direction["stage010_selected"].astype(bool)
            & pd.to_numeric(product_direction["realized_pnl"], errors="coerce").lt(0)
        ].copy()
        if not product_direction.empty and "stage010_selected" in product_direction.columns
        else pd.DataFrame()
    )
    if focus_windows.empty:
        decision = "stage011_no_remaining_negative_windows_stop"
        reason = "Stage010 已无剩余负窗口；应进入更严格真实引擎验真。"
    elif unexplained_loss_share < -50.0:
        decision = "stage011_remaining_tail_dominated_by_non_closed_quality_path_need_position_replay"
        reason = "窗口内 quality closed-lot PnL 为正，但基准曲线仍大幅亏损，剩余左尾更像未平仓/持仓路径或非 quality 事件主导，需要持仓级 replay。"
    elif not selected_negative.empty:
        decision = "stage011_selected_quality_has_negative_drag_need_true_engine_guard_audit"
        reason = "Stage010 选中质量事件中仍存在负贡献簇；只能做通用 guard 审计，不能做产品/方向黑名单。"
    else:
        decision = "stage011_remaining_tail_coverage_insufficient_need_new_pit_source"
        reason = "Stage010 加风险 delta 仍不足以覆盖剩余左尾，需要新 PIT 信息源或持仓级结构。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_stage": "Stage010",
        "target_variant": TARGET_VARIANT,
        "focus_window_count": int(len(focus_windows)),
        "top_n_focus_windows": TOP_N_FOCUS_WINDOWS,
        "total_stage010_loss_abs": total_loss_abs,
        "proxy_delta_in_focus_windows": proxy_delta,
        "proxy_delta_to_loss_abs_pct": proxy_loss_share,
        "selected_closed_lot_pnl_in_focus_windows": selected_pnl,
        "unselected_quality_event_pnl_in_focus_windows": unselected_pnl,
        "base_delta_minus_quality_event_pnl_in_focus_windows": unexplained,
        "base_delta_minus_quality_event_pnl_to_loss_abs_pct": unexplained_loss_share,
        "selected_negative_product_direction_count": int(len(selected_negative)),
        "selected_negative_product_direction_top": _json_safe(selected_negative.head(12).to_dict("records"))
        if not selected_negative.empty
        else [],
        "decision": decision,
        "decision_reason": reason,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
        "external_research_judgment": (
            "Meta-labeling and risk-sizing references support quality-based bet sizing, but the remaining drawdown must be "
            "attributed before adding more conditions. Trend-following right-tail references argue against cutting broad exposure "
            "without knowing whether the residual comes from open-position path, unselected opportunities, or selected negative drag."
        ),
        "overfit_reflection_before": (
            "否。本阶段只归因 Stage010 已冻结 proxy 的失败窗口，不新增交易参数、不按产品/方向做规则。"
        ),
        "overfit_reflection_after": (
            "否。输出是归因，不是交易规则；若据负贡献产品直接黑名单或调 rank/topN/25%，才会过拟合。"
        ),
        "continue_value_before": (
            "有价值。Stage010 是当前最强方向但未达目标，必须定位剩余左尾来源。"
        ),
        "continue_value_after": (
            "有价值。归因将决定下一步是持仓级 replay、真实引擎 guard 审计，还是转新 PIT 信息源。"
        ),
        "outputs": {
            "focus_windows": str(FOCUS_WINDOWS_PATH),
            "window_attribution": str(WINDOW_ATTRIBUTION_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _plot(window_attr: pd.DataFrame, product_direction: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 7), constrained_layout=True)
    if not window_attr.empty:
        shown = window_attr.head(24).copy()
        labels = shown["source_start_month"].astype(str) + "\n" + shown["start_date"].astype(str)
        x = np.arange(len(shown))
        axes[0].bar(x, shown["base_equity_delta"], label="base delta", color="#ef4444", alpha=0.75)
        axes[0].bar(x, shown["proxy_delta_in_window"], bottom=shown["base_equity_delta"], label="Stage010 proxy delta", color="#16a34a", alpha=0.75)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(labels, rotation=80, ha="right", fontsize=7)
        axes[0].set_title("Focus Window Base Delta + Stage010 Proxy Delta")
        axes[0].grid(True, axis="y", alpha=0.25)
        axes[0].legend(fontsize=8)
    if not product_direction.empty:
        selected = product_direction[product_direction["stage010_selected"].astype(bool)].sort_values("realized_pnl").head(16)
        labels = selected["product"].astype(str) + " " + selected["direction"].astype(str)
        axes[1].barh(np.arange(len(selected)), selected["realized_pnl"], color="#0f766e")
        axes[1].set_yticks(np.arange(len(selected)))
        axes[1].set_yticklabels(labels, fontsize=8)
        axes[1].invert_yaxis()
        axes[1].axvline(0.0, color="#111827", linewidth=0.8)
        axes[1].set_title("Selected Lot PnL In Focus Windows")
        axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], window_attr: pd.DataFrame, product_direction: pd.DataFrame, source_summary: pd.DataFrame) -> None:
    selected_negative = (
        product_direction[
            product_direction["stage010_selected"].astype(bool)
            & pd.to_numeric(product_direction["realized_pnl"], errors="coerce").lt(0)
        ].copy()
        if not product_direction.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage011 - Stage010 剩余左尾归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 核心结论",
        "",
        f"- focus windows：`{decision['focus_window_count']}`",
        f"- Stage010 focus loss abs：`{decision['total_stage010_loss_abs']:,.2f}`",
        f"- proxy delta / loss abs：`{decision['proxy_delta_to_loss_abs_pct']:.4f}%`",
        f"- selected closed-lot PnL：`{decision['selected_closed_lot_pnl_in_focus_windows']:,.2f}`",
        f"- unselected quality event PnL：`{decision['unselected_quality_event_pnl_in_focus_windows']:,.2f}`",
        f"- base delta minus quality-event PnL：`{decision['base_delta_minus_quality_event_pnl_in_focus_windows']:,.2f}` (`{decision['base_delta_minus_quality_event_pnl_to_loss_abs_pct']:.4f}%` of focus loss abs)",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## Source Summary",
        "",
        _md_table(source_summary, max_rows=20),
        "",
        "## Focus Windows",
        "",
        _md_table(window_attr.head(24), max_rows=24),
        "",
        "## Selected Negative Product/Direction",
        "",
        _md_table(selected_negative.head(20), max_rows=20),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], window_attr: pd.DataFrame, product_direction: pd.DataFrame, source_summary: pd.DataFrame) -> None:
    selected_negative = (
        product_direction[
            product_direction["stage010_selected"].astype(bool)
            & pd.to_numeric(product_direction["realized_pnl"], errors="coerce").lt(0)
        ].copy()
        if not product_direction.empty
        else pd.DataFrame()
    )
    record = f"""# Stage011 Stage010 剩余左尾归因

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段不跑新资金曲线，只归因 Stage010 失败窗口

## 外部调研与判断

- 参考资料：meta-labeling bet sizing、trend-following right-tail/drawdown attribution、pysystemtrade capital correction。
- 我的判断：Stage010 已证明质量加风险有信息量，但剩余左尾必须先分清是持仓路径、覆盖不足还是选中负贡献，不能继续扫 `25%/rank/topN/产品/方向`。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage011_stage010_remaining_left_tail_attribution.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage011_stage010_remaining_left_tail_attribution.py`
- 新增参数：`TOP_N_FOCUS_WINDOWS={TOP_N_FOCUS_WINDOWS}`、`TARGET_VARIANT={TARGET_VARIANT}`
- 修改参数：无
- 删除参数：无

## 结果

- focus windows：`{decision["focus_window_count"]}`
- Stage010 focus loss abs：`{decision["total_stage010_loss_abs"]:,.2f}`
- proxy delta / loss abs：`{decision["proxy_delta_to_loss_abs_pct"]:.4f}%`
- selected closed-lot PnL：`{decision["selected_closed_lot_pnl_in_focus_windows"]:,.2f}`
- unselected quality event PnL：`{decision["unselected_quality_event_pnl_in_focus_windows"]:,.2f}`
- base delta minus quality-event PnL：`{decision["base_delta_minus_quality_event_pnl_in_focus_windows"]:,.2f}`，占 focus loss abs `{decision["base_delta_minus_quality_event_pnl_to_loss_abs_pct"]:.4f}%`
- 选中负贡献 product/direction 数：`{decision["selected_negative_product_direction_count"]}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## Source Summary

{_md_table(source_summary, max_rows=20)}

## Selected Negative Product/Direction

{_md_table(selected_negative.head(20), max_rows=20)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}
- 原因：本阶段只归因，不产生交易规则；若直接按产品/方向负贡献做黑名单就是过拟合。

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- focus_windows: `{decision["outputs"]["focus_windows"]}`
- window_attribution: `{decision["outputs"]["window_attribution"]}`
- product_direction: `{decision["outputs"]["product_direction"]}`
- source_summary: `{decision["outputs"]["source_summary"]}`
- chart: `{decision["outputs"]["chart"]}`
- decision: `{decision["outputs"]["decision"]}`
- report: `{decision["outputs"]["report"]}`
"""
    STAGE_RECORD_PATH.write_text(record, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    curves = _read_csv(STAGE010_CURVES_PATH, parse_dates=["date"])
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "stage010_account_equity", "stage010_cum_delta"]:
        curves[column] = pd.to_numeric(curves[column], errors="coerce")
    lot_deltas = _read_csv(STAGE010_LOT_DELTAS_PATH, parse_dates=["exit_date"])
    quality_events = _read_csv(STAGE009_EVENTS_PATH, parse_dates=["exit_date"])
    worst = _read_csv(STAGE010_WORST_WINDOWS_PATH)
    focus = select_focus_windows(worst)
    window_attr = build_window_attribution(focus, curves, lot_deltas, quality_events)
    product_direction = build_product_direction_attribution(focus, lot_deltas, quality_events)
    source_summary = build_source_summary(window_attr)
    decision = make_decision(focus, window_attr, product_direction)

    focus.to_csv(FOCUS_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    window_attr.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    product_direction.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(window_attr, product_direction)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, window_attr, product_direction, source_summary)
    _write_stage_record(decision, window_attr, product_direction, source_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()

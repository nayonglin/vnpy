from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage023"
MODEL_TAG = "stage023_stage022_residual_window_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage023_stage022_residual_window_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage023_stage022_residual_window_attribution"

STAGE022_OUTPUT_DIR = LINE_DIR / "outputs" / "stage022_xsmom_entry_confirmation_proxy"
STAGE022_PREFIX = "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy"
STAGE022_TAG = "stage022_xsmom_entry_confirmation_proxy_v1"

CURVES_PATH = STAGE022_OUTPUT_DIR / f"{STAGE022_PREFIX}_curves_{STAGE022_TAG}.csv"
WORST_WINDOWS_PATH = STAGE022_OUTPUT_DIR / f"{STAGE022_PREFIX}_goal_worst_windows_{STAGE022_TAG}.csv"
LOT_DELTAS_PATH = STAGE022_OUTPUT_DIR / f"{STAGE022_PREFIX}_lot_deltas_{STAGE022_TAG}.csv.gz"
DECISION_PATH_STAGE022 = STAGE022_OUTPUT_DIR / f"{STAGE022_PREFIX}_decision_{STAGE022_TAG}.json"

FOCUS_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_focus_windows_{MODEL_TAG}.csv"
WINDOW_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
DAILY_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_detail_{MODEL_TAG}.csv.gz"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_component_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0624_stage023_stage022_residual_window_attribution.md"

TARGET_CONDITION = "stage013_guarded_quality_xsmom12_not_opposed"
TARGET_VARIANT = f"stage022_{TARGET_CONDITION}"
TOP_N_FOCUS_WINDOWS = 256


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
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无_"
    return frame.head(max_rows).to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _effect_label(value: float, eps: float = 1e-9) -> str:
    if value > eps:
        return "helped"
    if value < -eps:
        return "dragged"
    return "neutral"


def select_focus_windows(
    worst_windows: pd.DataFrame,
    *,
    target_variant: str = TARGET_VARIANT,
    top_n: int = TOP_N_FOCUS_WINDOWS,
) -> pd.DataFrame:
    data = worst_windows.copy()
    data["variant"] = data["variant"].astype(str)
    data["return_pct"] = pd.to_numeric(data["return_pct"], errors="coerce")
    data = data[data["variant"].eq(target_variant) & data["return_pct"].lt(0.0)].copy()
    if data.empty:
        return data
    for column in ["start_date", "end_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    data["source_start_month"] = data["source_start_month"].astype(str)
    data = data.dropna(subset=["start_date", "end_date"]).sort_values("return_pct", ascending=True)
    keys = ["variant", "source_start_month", "start_date", "end_date"]
    return data.drop_duplicates(keys).head(top_n).reset_index(drop=True)


def _prepare_target_curves(curves: pd.DataFrame, *, target_condition: str = TARGET_CONDITION) -> pd.DataFrame:
    data = curves.copy()
    if "condition" not in data.columns:
        data["condition"] = data.get("variant", "")
    data["condition"] = data["condition"].astype(str)
    data = data[data["condition"].eq(target_condition)].copy()
    if data.empty:
        raise ValueError(f"missing target condition in curves: {target_condition}")
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["requested_start_month", "date"])
    data["account_equity"] = _numeric(data, "account_equity")
    data["net_pnl"] = _numeric(data, "net_pnl")
    data["stage022_daily_delta"] = _numeric(data, "stage022_daily_delta")
    data["variant_daily_net_pnl"] = data["net_pnl"] + data["stage022_daily_delta"]
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def _prepare_lot_deltas(
    lot_deltas: pd.DataFrame,
    *,
    target_condition: str = TARGET_CONDITION,
) -> pd.DataFrame:
    if lot_deltas.empty:
        return lot_deltas.copy()
    data = lot_deltas.copy()
    if "condition" in data.columns:
        data["condition"] = data["condition"].astype(str)
        data = data[data["condition"].eq(target_condition)].copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["requested_start_month", "exit_date"])
    data["realized_pnl"] = _numeric(data, "realized_pnl")
    data["stage022_proxy_delta_pnl"] = _numeric(data, "stage022_proxy_delta_pnl")
    return data.reset_index(drop=True)


def _curve_at(curves: pd.DataFrame, source: str, date: pd.Timestamp) -> pd.Series:
    row = curves[curves["requested_start_month"].eq(source) & curves["date"].eq(date)]
    if row.empty:
        raise ValueError(f"missing target curve row source={source} date={date.date().isoformat()}")
    return row.iloc[0]


def _curve_segment(curves: pd.DataFrame, source: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return curves[
        curves["requested_start_month"].eq(source)
        & curves["date"].gt(start)
        & curves["date"].le(end)
    ].copy()


def _lot_segment(lot_deltas: pd.DataFrame, source: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if lot_deltas.empty:
        return lot_deltas.copy()
    return lot_deltas[
        lot_deltas["requested_start_month"].eq(source)
        & lot_deltas["exit_date"].gt(start)
        & lot_deltas["exit_date"].le(end)
    ].copy()


def attribute_focus_window(
    window: pd.Series,
    curves: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> dict[str, Any]:
    target_curves = _prepare_target_curves(curves)
    target_deltas = _prepare_lot_deltas(lot_deltas)
    source = str(window["source_start_month"])
    start = _date(window["start_date"])
    end = _date(window["end_date"])
    start_row = _curve_at(target_curves, source, start)
    end_row = _curve_at(target_curves, source, end)
    segment = _curve_segment(target_curves, source, start, end)
    lots = _lot_segment(target_deltas, source, start, end)

    start_equity = float(start_row["account_equity"])
    end_equity = float(end_row["account_equity"])
    variant_delta = end_equity - start_equity
    base_net_pnl = float(segment["net_pnl"].sum()) if not segment.empty else 0.0
    stage022_delta = float(segment["stage022_daily_delta"].sum()) if not segment.empty else 0.0
    component_sum = base_net_pnl + stage022_delta
    lot_proxy_delta = float(lots["stage022_proxy_delta_pnl"].sum()) if not lots.empty else 0.0
    lot_realized_pnl = float(lots["realized_pnl"].sum()) if not lots.empty else 0.0
    loss_abs = abs(variant_delta) if variant_delta < 0 else 0.0

    return {
        "variant": str(window.get("variant", TARGET_VARIANT)),
        "source_start_month": source,
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "return_pct": float(window.get("return_pct", np.nan)),
        "period_calendar_days": int(window.get("period_calendar_days", (end - start).days))
        if pd.notna(window.get("period_calendar_days", (end - start).days))
        else int((end - start).days),
        "period_trading_days": int(window.get("period_trading_days", len(segment)))
        if pd.notna(window.get("period_trading_days", len(segment)))
        else len(segment),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "variant_equity_delta": variant_delta,
        "base_net_pnl_in_window": base_net_pnl,
        "stage022_delta_in_window": stage022_delta,
        "component_sum_pnl": component_sum,
        "component_reconciliation_abs_diff": abs(variant_delta - component_sum),
        "selected_lot_count": int(len(lots)),
        "selected_lot_realized_pnl": lot_realized_pnl,
        "selected_lot_proxy_delta_pnl": lot_proxy_delta,
        "lot_delta_reconciliation_abs_diff": abs(stage022_delta - lot_proxy_delta),
        "stage022_component_effect": _effect_label(stage022_delta),
        "base_net_pnl_to_loss_abs_pct": base_net_pnl / loss_abs * 100.0 if loss_abs > 1e-12 else np.nan,
        "stage022_delta_to_loss_abs_pct": stage022_delta / loss_abs * 100.0 if loss_abs > 1e-12 else np.nan,
        "selected_lot_realized_pnl_to_loss_abs_pct": lot_realized_pnl / loss_abs * 100.0 if loss_abs > 1e-12 else np.nan,
    }


def build_window_attribution(
    focus_windows: pd.DataFrame,
    curves: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> pd.DataFrame:
    target_curves = _prepare_target_curves(curves)
    target_deltas = _prepare_lot_deltas(lot_deltas)
    rows = [
        attribute_focus_window(row, target_curves, target_deltas)
        for _, row in focus_windows.iterrows()
    ]
    return pd.DataFrame(rows)


def build_daily_detail(focus_windows: pd.DataFrame, curves: pd.DataFrame) -> pd.DataFrame:
    target_curves = _prepare_target_curves(curves)
    rows: list[pd.DataFrame] = []
    for rank, (_, window) in enumerate(focus_windows.iterrows(), start=1):
        source = str(window["source_start_month"])
        start = _date(window["start_date"])
        end = _date(window["end_date"])
        segment = _curve_segment(target_curves, source, start, end)
        if segment.empty:
            continue
        detail = segment[
            [
                "requested_start_month",
                "date",
                "account_equity",
                "net_pnl",
                "stage022_daily_delta",
                "variant_daily_net_pnl",
            ]
        ].copy()
        detail["selected_rank"] = rank
        detail["window_id"] = f"{rank:03d}_{source}_{start.date().isoformat()}_{end.date().isoformat()}"
        detail["window_start_date"] = start.date().isoformat()
        detail["window_end_date"] = end.date().isoformat()
        detail["window_return_pct"] = float(window.get("return_pct", np.nan))
        detail["stage022_daily_effect"] = detail["stage022_daily_delta"].map(_effect_label)
        rows.append(detail)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_source_summary(window_attribution: pd.DataFrame) -> pd.DataFrame:
    if window_attribution.empty:
        return pd.DataFrame()
    grouped = (
        window_attribution.groupby("source_start_month", dropna=False)
        .agg(
            window_count=("source_start_month", "size"),
            worst_return_pct=("return_pct", "min"),
            median_return_pct=("return_pct", "median"),
            variant_equity_delta=("variant_equity_delta", "sum"),
            base_net_pnl_in_window=("base_net_pnl_in_window", "sum"),
            stage022_delta_in_window=("stage022_delta_in_window", "sum"),
            selected_lot_count=("selected_lot_count", "sum"),
            selected_lot_realized_pnl=("selected_lot_realized_pnl", "sum"),
            max_component_reconciliation_abs_diff=("component_reconciliation_abs_diff", "max"),
            max_lot_delta_reconciliation_abs_diff=("lot_delta_reconciliation_abs_diff", "max"),
        )
        .reset_index()
        .sort_values(["worst_return_pct", "source_start_month"], ascending=[True, True])
    )
    grouped["stage022_component_effect"] = grouped["stage022_delta_in_window"].map(_effect_label)
    return grouped


def build_product_direction_summary(
    focus_windows: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> pd.DataFrame:
    target_deltas = _prepare_lot_deltas(lot_deltas)
    rows: list[pd.DataFrame] = []
    for rank, (_, window) in enumerate(focus_windows.iterrows(), start=1):
        source = str(window["source_start_month"])
        start = _date(window["start_date"])
        end = _date(window["end_date"])
        lots = _lot_segment(target_deltas, source, start, end)
        if lots.empty:
            continue
        lots = lots.copy()
        lots["selected_rank"] = rank
        lots["window_id"] = f"{rank:03d}_{source}_{start.date().isoformat()}_{end.date().isoformat()}"
        lots["window_return_pct"] = float(window.get("return_pct", np.nan))
        rows.append(lots)
    if not rows:
        return pd.DataFrame()
    detail = pd.concat(rows, ignore_index=True)
    return (
        detail.groupby(["product", "direction"], dropna=False)
        .agg(
            focus_window_lot_count=("lot_id", "size") if "lot_id" in detail.columns else ("product", "size"),
            affected_window_count=("window_id", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            stage022_proxy_delta_pnl=("stage022_proxy_delta_pnl", "sum"),
            worst_window_return_pct=("window_return_pct", "min"),
        )
        .reset_index()
        .sort_values(["stage022_proxy_delta_pnl", "realized_pnl"], ascending=[True, True])
    )


def plot_component_chart(source_summary: pd.DataFrame, path: Path) -> None:
    if source_summary.empty:
        return
    plot_data = source_summary.head(12).copy()
    x = np.arange(len(plot_data))
    width = 0.36
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(x - width / 2, plot_data["base_net_pnl_in_window"], width, label="base net pnl")
    ax.bar(x + width / 2, plot_data["stage022_delta_in_window"], width, label="stage022 delta")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(plot_data["source_start_month"].astype(str), rotation=45, ha="right")
    ax.set_title("Stage023 residual windows: base vs Stage022 delta")
    ax.set_ylabel("PnL sum across focus windows")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_report(decision: dict[str, Any], window_attribution: pd.DataFrame, source_summary: pd.DataFrame) -> str:
    lines = [
        "# Stage023 Stage022 剩余负窗口归因",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 聚焦窗口数：`{decision['focus_window_count']}`",
        f"- 最差窗口：`{decision['worst_window']}`",
        f"- focus variant equity delta：`{decision['focus_variant_equity_delta']:.4f}`",
        f"- focus base net pnl：`{decision['focus_base_net_pnl']:.4f}`",
        f"- focus Stage022 delta：`{decision['focus_stage022_delta']:.4f}`",
        f"- Stage022 delta / loss abs：`{decision['focus_stage022_delta_to_loss_abs_pct']:.4f}%`",
        f"- max component reconciliation abs diff：`{decision['max_component_reconciliation_abs_diff']:.8f}`",
        f"- max lot delta reconciliation abs diff：`{decision['max_lot_delta_reconciliation_abs_diff']:.8f}`",
        "",
        "## 源起点汇总",
        "",
        _md_table(source_summary, max_rows=20),
        "",
        "## 最差窗口归因样例",
        "",
        _md_table(window_attribution.head(20), max_rows=20),
        "",
    ]
    return "\n".join(lines)


def write_stage_record(decision: dict[str, Any], source_summary: pd.DataFrame) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    lines = [
        "# Stage023 Stage022 剩余负窗口归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{timestamp}",
        "- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否；本阶段不是候选规则，只判断 Stage022 改善剩余失败来自哪里",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：pyfolio drawdown/underwater period 归因、pysystemtrade capital correction / risk exposure 思路、趋势跟随 drawdown 文献。",
        "- 我的判断：Stage022 已经证明 xsmom 入场确认有增量，但目标仍失败；继续优化前必须先拆剩余负窗口，确认是 base 趋势持仓亏损、加风险 proxy 拖累，还是二者共同导致。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage023_stage022_residual_window_attribution.py`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage023_stage022_residual_window_attribution.py`",
        f"- 新增参数：`TARGET_VARIANT={TARGET_VARIANT}`、`TOP_N_FOCUS_WINDOWS={TOP_N_FOCUS_WINDOWS}`",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 输入窗口：Stage022 `goal_worst_windows` 中目标变体的负收益窗口，按收益从低到高取前 256 个。",
        "- 输入曲线：Stage022 `curves` 中 `stage013_guarded_quality_xsmom12_not_opposed` 条件曲线。",
        "- 输入 delta：Stage022 `lot_deltas` 中同一条件的退出日 proxy delta。",
        "- 口径：窗口内 `(start_date, end_date]` 的 base `net_pnl` 与 `stage022_daily_delta` 拆分，校验二者和是否等于权益变化。",
        "",
        "## 结果",
        "",
        f"- focus windows：`{decision['focus_window_count']}`",
        f"- worst window：`{decision['worst_window']}`",
        f"- focus variant equity delta：`{decision['focus_variant_equity_delta']:.4f}`",
        f"- focus base net pnl：`{decision['focus_base_net_pnl']:.4f}`",
        f"- focus Stage022 delta：`{decision['focus_stage022_delta']:.4f}`",
        f"- Stage022 delta / loss abs：`{decision['focus_stage022_delta_to_loss_abs_pct']:.4f}%`",
        f"- dragged window count：`{decision['dragged_window_count']}`",
        f"- helped window count：`{decision['helped_window_count']}`",
        f"- neutral window count：`{decision['neutral_window_count']}`",
        f"- max component reconciliation abs diff：`{decision['max_component_reconciliation_abs_diff']:.8f}`",
        f"- max lot delta reconciliation abs diff：`{decision['max_lot_delta_reconciliation_abs_diff']:.8f}`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 源起点汇总",
        "",
        _md_table(source_summary, max_rows=20),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只做固定 Stage022 最优变体的失败归因，不根据结果改阈值、品种、方向、lookback 或资金权重。",
        "- 运行后判断：否。本阶段没有产生新策略规则；如果拿归因中的具体产品/日期做黑名单，会变成过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage022 已显示结构性改善，剩余负窗口归因能决定下一步该转真实引擎还是换信息源。",
        f"- 运行后判断：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
        f"- focus_windows：`{FOCUS_WINDOWS_PATH}`",
        f"- window_attribution：`{WINDOW_ATTRIBUTION_PATH}`",
        f"- daily_detail：`{DAILY_DETAIL_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- product_direction_summary：`{PRODUCT_DIRECTION_SUMMARY_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
    ]
    return "\n".join(lines)


def run_stage() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    worst_windows = _read_csv(WORST_WINDOWS_PATH)
    curves = _read_csv(CURVES_PATH)
    lot_deltas = _read_csv(LOT_DELTAS_PATH)
    focus_windows = select_focus_windows(worst_windows)
    if focus_windows.empty:
        raise ValueError(f"no negative focus windows for {TARGET_VARIANT}")
    window_attribution = build_window_attribution(focus_windows, curves, lot_deltas)
    daily_detail = build_daily_detail(focus_windows, curves)
    source_summary = build_source_summary(window_attribution)
    product_direction_summary = build_product_direction_summary(focus_windows, lot_deltas)

    focus_loss_abs = float(
        window_attribution.loc[window_attribution["variant_equity_delta"].lt(0), "variant_equity_delta"].abs().sum()
    )
    focus_stage022_delta = float(window_attribution["stage022_delta_in_window"].sum())
    focus_base_net_pnl = float(window_attribution["base_net_pnl_in_window"].sum())
    focus_variant_equity_delta = float(window_attribution["variant_equity_delta"].sum())
    dragged = int(window_attribution["stage022_component_effect"].eq("dragged").sum())
    helped = int(window_attribution["stage022_component_effect"].eq("helped").sum())
    neutral = int(window_attribution["stage022_component_effect"].eq("neutral").sum())
    worst_row = window_attribution.sort_values("return_pct").iloc[0]
    stage022_drag_abs_pct = focus_stage022_delta / focus_loss_abs * 100.0 if focus_loss_abs > 1e-12 else np.nan
    if focus_stage022_delta < 0:
        decision_label = "stage023_stage022_residual_proxy_drag_needs_true_engine_guard"
        continue_value_after = "有价值但必须谨慎。focus 窗口中 Stage022 delta 为负，下一步应先查 proxy 拖累是否来自真实可避免路径，而不能直接加大风险。"
    elif focus_stage022_delta > 0:
        decision_label = "stage023_residual_loss_base_dominant_stage022_still_helping"
        continue_value_after = "有价值。focus 窗口中 Stage022 delta 仍在帮忙，剩余失败主要来自 base 趋势持仓路径，下一步应做真实引擎可实现性和 base residual 持仓归因。"
    else:
        decision_label = "stage023_residual_loss_base_dominant_stage022_neutral"
        continue_value_after = "有价值但不是突破。focus 窗口中 Stage022 delta 基本中性，下一步应转 base residual 持仓归因。"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_variant": TARGET_VARIANT,
        "target_condition": TARGET_CONDITION,
        "top_n_focus_windows": TOP_N_FOCUS_WINDOWS,
        "focus_window_count": int(len(focus_windows)),
        "worst_window": {
            "source_start_month": str(worst_row["source_start_month"]),
            "start_date": str(worst_row["start_date"]),
            "end_date": str(worst_row["end_date"]),
            "return_pct": float(worst_row["return_pct"]),
            "variant_equity_delta": float(worst_row["variant_equity_delta"]),
            "base_net_pnl_in_window": float(worst_row["base_net_pnl_in_window"]),
            "stage022_delta_in_window": float(worst_row["stage022_delta_in_window"]),
        },
        "focus_variant_equity_delta": focus_variant_equity_delta,
        "focus_loss_abs": focus_loss_abs,
        "focus_base_net_pnl": focus_base_net_pnl,
        "focus_stage022_delta": focus_stage022_delta,
        "focus_stage022_delta_to_loss_abs_pct": stage022_drag_abs_pct,
        "dragged_window_count": dragged,
        "helped_window_count": helped,
        "neutral_window_count": neutral,
        "max_component_reconciliation_abs_diff": float(window_attribution["component_reconciliation_abs_diff"].max()),
        "max_lot_delta_reconciliation_abs_diff": float(window_attribution["lot_delta_reconciliation_abs_diff"].max()),
        "decision": decision_label,
        "external_research_judgment": (
            "Drawdown attribution should identify whether the residual underwater period is caused by base trend exposure "
            "or by the overlay itself before adding more risk."
        ),
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
        "continue_value_after": continue_value_after,
        "input_paths": {
            "stage022_decision": str(DECISION_PATH_STAGE022),
            "worst_windows": str(WORST_WINDOWS_PATH),
            "curves": str(CURVES_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
        },
        "outputs": {
            "focus_windows": str(FOCUS_WINDOWS_PATH),
            "window_attribution": str(WINDOW_ATTRIBUTION_PATH),
            "daily_detail": str(DAILY_DETAIL_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }

    focus_windows.to_csv(FOCUS_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    window_attribution.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    daily_detail.to_csv(DAILY_DETAIL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_direction_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    plot_component_chart(source_summary, CHART_PATH)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(write_report(decision, window_attribution, source_summary), encoding="utf-8")
    STAGE_RECORD_PATH.write_text(write_stage_record(decision, source_summary), encoding="utf-8")
    return decision


if __name__ == "__main__":
    result = run_stage()
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2))

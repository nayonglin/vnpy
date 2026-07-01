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
STAGE = "Stage012"
MODEL_TAG = "stage012_entry_state_diagnostic_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage012_entry_state_diagnostic"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage012_entry_state_diagnostic"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
STAGE011_OUTPUT_DIR = LINE_DIR / "outputs" / "stage011_focus_window_position_pnl"

STAGE006_CURVES_PATH = (
    STAGE006_OUTPUT_DIR
    / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv"
)
STAGE011_CURVES_PATH = (
    STAGE011_OUTPUT_DIR
    / "rebuilt_c9_stage011_focus_window_position_pnl_curves_stage011_focus_window_position_pnl_v1.csv"
)
WINDOW_POSITION_DETAIL_PATH = (
    STAGE011_OUTPUT_DIR
    / "rebuilt_c9_stage011_focus_window_position_pnl_window_position_detail_stage011_focus_window_position_pnl_v1.csv"
)
QUALITY_FEATURES_PATH = (
    STAGE007_OUTPUT_DIR
    / "rebuilt_c9_stage007_minute_source_coverage_rebind_quality_features_stage007_minute_source_coverage_rebind_v1.csv"
)
STAGE011_DECISION_PATH = (
    STAGE011_OUTPUT_DIR
    / "rebuilt_c9_stage011_focus_window_position_pnl_decision_stage011_focus_window_position_pnl_v1.json"
)

DAILY_STATE_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_state_detail_{MODEL_TAG}.csv"
DAILY_STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_state_summary_{MODEL_TAG}.csv"
ENTRY_STATE_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_state_detail_{MODEL_TAG}.csv"
ENTRY_DIMENSION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_dimension_summary_{MODEL_TAG}.csv"
ENTRY_COMBO_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_combo_summary_{MODEL_TAG}.csv"
BASELINE_COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_baseline_comparison_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FOCUS_SOURCE_BUCKET = "opened_or_traded_after_focus_start"
BASELINE_START = pd.Timestamp("2020-01-01")


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _decision_inputs() -> tuple[pd.Timestamp, pd.Timestamp, list[str]]:
    decision = json.loads(STAGE011_DECISION_PATH.read_text(encoding="utf-8"))
    focus_start = pd.Timestamp(decision["focus_start"]).normalize()
    focus_end = pd.Timestamp(decision["focus_end"]).normalize()
    sources = pd.read_csv(
        STAGE011_OUTPUT_DIR / "rebuilt_c9_stage011_focus_window_position_pnl_validation_stage011_focus_window_position_pnl_v1.csv",
        encoding="utf-8-sig",
        usecols=["source_start_month"],
    )["source_start_month"].astype(str).drop_duplicates().sort_values().tolist()
    return focus_start, focus_end, sources


def _drawdown_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    if number >= -10.0:
        return "dd_ge_-10"
    if number >= -20.0:
        return "dd_-10_-20"
    if number >= -30.0:
        return "dd_-20_-30"
    if number >= -40.0:
        return "dd_-30_-40"
    return "dd_lt_-40"


def _broker_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    if number < 30.0:
        return "broker_lt30"
    if number < 50.0:
        return "broker_30_50"
    if number < 70.0:
        return "broker_50_70"
    if number < 90.0:
        return "broker_70_90"
    return "broker_ge90"


def _active_products_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = int(number)
    if number <= 0:
        return "products_0"
    if number == 1:
        return "products_1"
    if number == 2:
        return "products_2"
    if number == 3:
        return "products_3"
    return "products_ge4"


def _same_direction_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "same_dir_missing"
    number = int(number)
    if number <= 0:
        return "same_dir_0"
    if number == 1:
        return "same_dir_1"
    return "same_dir_ge2"


def _same_corr_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "corr_missing"
    number = float(number)
    if number < 0.3:
        return "corr_lt0.3"
    if number < 0.6:
        return "corr_0.3_0.6"
    return "corr_ge0.6"


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


def _previous_state(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in [
        "account_equity",
        "broker10_margin_to_equity_pct",
        "drawdown_pct",
        "c3_active_products",
        "c3_active_contracts",
        "trade_count",
        "net_pnl",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    data = data.sort_values(["requested_start_month", "date"]).dropna(subset=["date"])
    rows = []
    for source, group in data.groupby("requested_start_month", sort=True):
        g = group.copy()
        keep = g[["requested_start_month", "date"]].copy()
        for column in [
            "account_equity",
            "broker10_margin_to_equity_pct",
            "drawdown_pct",
            "c3_active_products",
            "c3_active_contracts",
            "trade_count",
            "net_pnl",
        ]:
            keep[f"prev_{column}"] = g[column].shift(1)
        rows.append(keep)
    state = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    state["prev_drawdown_bucket"] = state["prev_drawdown_pct"].map(_drawdown_bucket)
    state["prev_broker_bucket"] = state["prev_broker10_margin_to_equity_pct"].map(_broker_bucket)
    state["prev_active_products_bucket"] = state["prev_c3_active_products"].map(_active_products_bucket)
    return state


def _daily_state_detail(focus_start: pd.Timestamp, focus_end: pd.Timestamp) -> pd.DataFrame:
    curves = pd.read_csv(STAGE011_CURVES_PATH, encoding="utf-8-sig")
    state = _previous_state(curves)
    detail = pd.read_csv(WINDOW_POSITION_DETAIL_PATH, encoding="utf-8-sig")
    detail["date"] = pd.to_datetime(detail["date"], errors="coerce").dt.normalize()
    detail = detail[
        detail["source_bucket"].eq(FOCUS_SOURCE_BUCKET)
        & detail["date"].gt(focus_start)
        & detail["date"].le(focus_end)
    ].copy()
    for column in ["net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "end_pos", "start_pos", "pos_change"]:
        detail[column] = pd.to_numeric(detail.get(column, 0.0), errors="coerce").fillna(0.0)
    detail = detail.merge(state, on=["requested_start_month", "date"], how="left")
    detail["pnl_sign"] = np.where(detail["net_pnl"] < 0.0, "loss_day_position", "profit_or_flat_day_position")
    detail["product_direction"] = detail["product"].astype(str) + " " + detail["direction"].astype(str)
    return detail.sort_values(["requested_start_month", "date", "product_direction"]).reset_index(drop=True)


def _entry_state_detail(focus_start: pd.Timestamp, focus_end: pd.Timestamp, sources: list[str]) -> pd.DataFrame:
    curves = pd.read_csv(STAGE006_CURVES_PATH, encoding="utf-8-sig")
    state = _previous_state(curves)
    features = pd.read_csv(QUALITY_FEATURES_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    for column in [
        "realized_pnl",
        "r_multiple",
        "volume",
        "risk_amount",
        "ai_product_pool_rank",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "active_positions_before",
        "loss_streak",
    ]:
        features[column] = pd.to_numeric(features.get(column, np.nan), errors="coerce")
    data = features[features["requested_start_month"].astype(str).isin(sources)].copy()
    data = data[data["entry_date"].ge(BASELINE_START)].copy()
    data["scope"] = np.where(
        data["entry_date"].gt(focus_start) & data["entry_date"].le(focus_end),
        "focus_after_start_entries",
        "baseline_2020plus_entries",
    )
    data = data.merge(
        state.rename(columns={"date": "entry_date"}),
        on=["requested_start_month", "entry_date"],
        how="left",
    )
    data["quality_bucket"] = data.apply(_quality_bucket, axis=1)
    data["same_direction_count_bucket"] = data["same_direction_correlation_active_count"].map(_same_direction_bucket)
    data["same_direction_corr_bucket"] = data["same_direction_correlation_max_corr"].map(_same_corr_bucket)
    data["winner"] = data["realized_pnl"].gt(0.0).astype(int)
    data["loss"] = data["realized_pnl"].lt(0.0).astype(int)
    data["entry_month"] = data["entry_date"].dt.to_period("M").astype(str)
    data["entry_product_direction"] = data["product"].astype(str) + " " + data["direction"].astype(str)
    return data.sort_values(["scope", "requested_start_month", "entry_date", "entry_product_direction"]).reset_index(drop=True)


def _daily_state_summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    dimensions = [
        "prev_drawdown_bucket",
        "prev_broker_bucket",
        "prev_active_products_bucket",
        "product_direction",
    ]
    for dimension in dimensions:
        if dimension not in detail.columns:
            continue
        summary = (
            detail.groupby(dimension, dropna=False)
            .agg(
                row_count=("net_pnl", "size"),
                source_count=("requested_start_month", "nunique"),
                day_count=("date", "nunique"),
                net_pnl=("net_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                slippage=("slippage", "sum"),
                trade_count=("trade_count", "sum"),
                avg_prev_drawdown_pct=("prev_drawdown_pct", "mean"),
                avg_prev_broker10_pct=("prev_broker10_margin_to_equity_pct", "mean"),
            )
            .reset_index()
            .rename(columns={dimension: "bucket"})
        )
        summary.insert(0, "dimension", dimension)
        rows.append(summary)
    output = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    if output.empty:
        return output
    output["loss_abs"] = output["net_pnl"].clip(upper=0.0).abs()
    return output.sort_values(["dimension", "net_pnl"]).reset_index(drop=True)


def _entry_dimension_summary(entries: pd.DataFrame) -> pd.DataFrame:
    dimensions = [
        "prev_drawdown_bucket",
        "prev_broker_bucket",
        "prev_active_products_bucket",
        "active_positions_bucket",
        "ai_rank_bucket",
        "quality_bucket",
        "same_direction_count_bucket",
        "same_direction_corr_bucket",
        "risk_multiplier_bucket",
        "loss_streak_bucket",
    ]
    rows: list[pd.DataFrame] = []
    for scope, scope_data in entries.groupby("scope", sort=False):
        for dimension in dimensions:
            if dimension not in scope_data.columns:
                continue
            summary = (
                scope_data.groupby(dimension, dropna=False)
                .agg(
                    lot_count=("lot_id", "count"),
                    source_count=("requested_start_month", "nunique"),
                    product_count=("product", "nunique"),
                    realized_pnl=("realized_pnl", "sum"),
                    avg_r_multiple=("r_multiple", "mean"),
                    win_rate_pct=("winner", lambda s: float(s.mean() * 100.0) if len(s) else np.nan),
                    avg_ai_rank=("ai_product_pool_rank", "mean"),
                    avg_prev_drawdown_pct=("prev_drawdown_pct", "mean"),
                    avg_prev_broker10_pct=("prev_broker10_margin_to_equity_pct", "mean"),
                )
                .reset_index()
                .rename(columns={dimension: "bucket"})
            )
            summary.insert(0, "dimension", dimension)
            summary.insert(0, "scope", scope)
            rows.append(summary)
    output = pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()
    if output.empty:
        return output
    output["realized_pnl_per_lot"] = output["realized_pnl"] / output["lot_count"].replace(0, np.nan)
    return output.sort_values(["scope", "dimension", "realized_pnl"]).reset_index(drop=True)


def _entry_combo_summary(entries: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "scope",
        "prev_drawdown_bucket",
        "prev_broker_bucket",
        "prev_active_products_bucket",
        "ai_rank_bucket",
        "quality_bucket",
    ]
    output = (
        entries.groupby(keys, dropna=False)
        .agg(
            lot_count=("lot_id", "count"),
            source_count=("requested_start_month", "nunique"),
            realized_pnl=("realized_pnl", "sum"),
            avg_r_multiple=("r_multiple", "mean"),
            win_rate_pct=("winner", lambda s: float(s.mean() * 100.0) if len(s) else np.nan),
            avg_ai_rank=("ai_product_pool_rank", "mean"),
            avg_prev_drawdown_pct=("prev_drawdown_pct", "mean"),
            avg_prev_broker10_pct=("prev_broker10_margin_to_equity_pct", "mean"),
        )
        .reset_index()
    )
    output["realized_pnl_per_lot"] = output["realized_pnl"] / output["lot_count"].replace(0, np.nan)
    return output.sort_values(["scope", "realized_pnl"]).reset_index(drop=True)


def _baseline_comparison(entry_summary: pd.DataFrame) -> pd.DataFrame:
    focus = entry_summary[entry_summary["scope"].eq("focus_after_start_entries")].copy()
    baseline = entry_summary[entry_summary["scope"].eq("baseline_2020plus_entries")].copy()
    merged = focus.merge(
        baseline,
        on=["dimension", "bucket"],
        how="left",
        suffixes=("_focus", "_baseline"),
    )
    if merged.empty:
        return merged
    merged["pnl_per_lot_delta_focus_minus_baseline"] = (
        merged["realized_pnl_per_lot_focus"] - merged["realized_pnl_per_lot_baseline"]
    )
    merged["win_rate_delta_focus_minus_baseline"] = merged["win_rate_pct_focus"] - merged["win_rate_pct_baseline"]
    return merged.sort_values("realized_pnl_focus").reset_index(drop=True)


def _plot(daily_summary: pd.DataFrame, entry_summary: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)

    ax = axes[0, 0]
    dd = daily_summary[daily_summary["dimension"].eq("prev_drawdown_bucket")].copy()
    if not dd.empty:
        ax.barh(dd["bucket"], dd["net_pnl"], color=np.where(dd["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("Focus Daily PnL By Previous Drawdown Bucket")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[0, 1]
    broker = daily_summary[daily_summary["dimension"].eq("prev_broker_bucket")].copy()
    if not broker.empty:
        ax.barh(broker["bucket"], broker["net_pnl"], color=np.where(broker["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("Focus Daily PnL By Previous Broker10 Bucket")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 0]
    focus_quality = entry_summary[
        entry_summary["scope"].eq("focus_after_start_entries") & entry_summary["dimension"].eq("quality_bucket")
    ].copy()
    if not focus_quality.empty:
        ax.barh(
            focus_quality["bucket"],
            focus_quality["realized_pnl"],
            color=np.where(focus_quality["realized_pnl"].ge(0), "#2563eb", "#f97316"),
        )
    ax.set_title("Focus Entry Realized PnL By Quality Bucket")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 1]
    if not comparison.empty:
        view = comparison[comparison["dimension"].isin(["prev_drawdown_bucket", "ai_rank_bucket", "quality_bucket"])].head(20)
        labels = view["dimension"].astype(str) + "\n" + view["bucket"].astype(str)
        ax.barh(labels, view["pnl_per_lot_delta_focus_minus_baseline"], color="#7c3aed")
    ax.set_title("Focus Minus Baseline PnL Per Lot Delta")
    ax.set_xlabel("delta")
    ax.grid(True, axis="x", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    daily_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
    combo: pd.DataFrame,
    comparison: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 新增/交易仓位入场前账户状态诊断",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读诊断；不改策略、不扫参数、不连接 CTP、不调用下单。",
        f"- 焦点窗口：`{decision['focus_start']}` 到 `{decision['focus_end']}`。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随资料支持用账户风险、市场波动、持仓集中度做风控输入，但不支持围绕单个坏窗口做品种或日期黑名单。",
        "- PBO 资料要求把焦点窗口状态与基准样本对照，避免把局部坏状态误认为稳定规律。",
        "",
        "## 日级新增/交易仓位状态",
        "",
        _md_table(daily_summary, max_rows=50),
        "",
        "## 入场逐笔状态",
        "",
        _md_table(entry_summary, max_rows=60),
        "",
        "## 入场状态组合",
        "",
        _md_table(combo, max_rows=40),
        "",
        "## 焦点 vs 基准对照",
        "",
        _md_table(comparison, max_rows=60),
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
    focus_start, focus_end, sources = _decision_inputs()

    daily_detail = _daily_state_detail(focus_start, focus_end)
    daily_summary = _daily_state_summary(daily_detail)
    entry_detail = _entry_state_detail(focus_start, focus_end, sources)
    entry_summary = _entry_dimension_summary(entry_detail)
    combo = _entry_combo_summary(entry_detail)
    comparison = _baseline_comparison(entry_summary)
    _plot(daily_summary, entry_summary, comparison)

    daily_detail.to_csv(DAILY_STATE_DETAIL_PATH, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(DAILY_STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_detail.to_csv(ENTRY_STATE_DETAIL_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_DIMENSION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    combo.to_csv(ENTRY_COMBO_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(BASELINE_COMPARISON_PATH, index=False, encoding="utf-8-sig")

    focus_entries = entry_detail[entry_detail["scope"].eq("focus_after_start_entries")].copy()
    focus_entry_pnl = float(focus_entries["realized_pnl"].sum()) if not focus_entries.empty else 0.0
    focus_entry_count = int(len(focus_entries))
    daily_loss = float(daily_detail["net_pnl"].sum()) if not daily_detail.empty else 0.0
    worst_daily_state = daily_summary.iloc[0].to_dict() if not daily_summary.empty else {}
    worst_entry_dimension = entry_summary[entry_summary["scope"].eq("focus_after_start_entries")].iloc[0].to_dict()
    worst_comparison = comparison.iloc[0].to_dict() if not comparison.empty else {}

    decision_label = "stage012_state_diagnostic_no_rule_yet_focus_loss_state_identified"
    core_attribution = (
        f"焦点窗口新增/交易仓位日级净 PnL {daily_loss:,.2f}；"
        f"焦点窗口入场 lot {focus_entry_count} 笔，完整 realized_pnl {focus_entry_pnl:,.2f}。"
        f"日级最差状态维度为 {worst_daily_state.get('dimension', 'NA')}={worst_daily_state.get('bucket', 'NA')}，"
        f"net_pnl={float(worst_daily_state.get('net_pnl', np.nan)):,.2f}；"
        f"入场逐笔最差维度为 {worst_entry_dimension.get('dimension', 'NA')}={worst_entry_dimension.get('bucket', 'NA')}，"
        f"realized_pnl={float(worst_entry_dimension.get('realized_pnl', np.nan)):,.2f}。"
        f"相对基准最差对照为 {worst_comparison.get('dimension', 'NA')}={worst_comparison.get('bucket', 'NA')}，"
        f"pnl_per_lot_delta={float(worst_comparison.get('pnl_per_lot_delta_focus_minus_baseline', np.nan)):,.2f}。"
    )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "focus_start": focus_start.date().isoformat(),
        "focus_end": focus_end.date().isoformat(),
        "source_count": int(len(sources)),
        "daily_detail_rows": int(len(daily_detail)),
        "entry_detail_rows": int(len(entry_detail)),
        "focus_entry_count": focus_entry_count,
        "focus_entry_realized_pnl": focus_entry_pnl,
        "focus_daily_net_pnl": daily_loss,
        "worst_daily_state": _json_safe(worst_daily_state),
        "worst_entry_dimension": _json_safe(worst_entry_dimension),
        "worst_baseline_comparison": _json_safe(worst_comparison),
        "decision": decision_label,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Account state, volatility and concentration are valid risk-management inputs, but this stage remains diagnostic. "
            "No product/date blacklist or threshold rule is promoted from a single left-tail window."
        ),
        "overfit_reflection_before": (
            "否。Stage012 只看交易前可见状态分布，并和 2020+ 基准样本对照，不新增规则。"
        ),
        "continue_value_before": (
            "是。Stage011 已确认新增/交易仓位占左尾亏损 61.92%，必须找这些仓位入场前的可见状态。"
        ),
        "core_attribution": core_attribution,
        "overfit_reflection_after": (
            "否。本阶段没有把任何状态桶变成阈值，只输出焦点与基准对照。"
        ),
        "continue_value_after": (
            "有。若某些账户状态在焦点和基准中均显示不良，下一步才值得冻结一个账户状态闸门并写真引擎验证。"
        ),
        "outputs": {
            "daily_state_detail": str(DAILY_STATE_DETAIL_PATH),
            "daily_state_summary": str(DAILY_STATE_SUMMARY_PATH),
            "entry_state_detail": str(ENTRY_STATE_DETAIL_PATH),
            "entry_dimension_summary": str(ENTRY_DIMENSION_SUMMARY_PATH),
            "entry_combo_summary": str(ENTRY_COMBO_SUMMARY_PATH),
            "baseline_comparison": str(BASELINE_COMPARISON_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, daily_summary, entry_summary, combo, comparison)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("daily_state_summary")
    print(daily_summary.head(40).to_string(index=False))
    print("entry_dimension_summary")
    print(entry_summary.head(60).to_string(index=False))
    print("baseline_comparison")
    print(comparison.head(40).to_string(index=False))


if __name__ == "__main__":
    main()

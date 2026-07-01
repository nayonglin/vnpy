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
import stage010_worst_window_attribution as s010

import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage011"
MODEL_TAG = "stage011_focus_window_position_pnl_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage011_focus_window_position_pnl"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage011_focus_window_position_pnl"
STAGE008_OUTPUT_DIR = LINE_DIR / "outputs" / "stage008_high_quality_add_risk_proxy"
STAGE010_OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_worst_window_attribution"

REFERENCE_CURVES_PATH = (
    STAGE008_OUTPUT_DIR
    / "rebuilt_c9_stage008_high_quality_add_risk_proxy_curves_stage008_high_quality_add_risk_proxy_v1.csv"
)
STAGE010_FOCUS_WINDOWS_PATH = (
    STAGE010_OUTPUT_DIR
    / "rebuilt_c9_stage010_worst_window_attribution_focus_windows_stage010_worst_window_attribution_v1.csv"
)
STAGE010_DECISION_PATH = (
    STAGE010_OUTPUT_DIR
    / "rebuilt_c9_stage010_worst_window_attribution_decision_stage010_worst_window_attribution_v1.json"
)

CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
WINDOW_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_position_detail_{MODEL_TAG}.csv"
SOURCE_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_bucket_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
DAILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_summary_{MODEL_TAG}.csv"
VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

BROKER10_MULTIPLIER = 1.10


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _month_start(month: Any) -> pd.Timestamp:
    return pd.Timestamp(f"{str(month)[:7]}-01").normalize()


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def _direction_from_pos(start_pos: float, end_pos: float) -> str:
    pos = start_pos if abs(start_pos) > 1e-9 else end_pos
    if pos > 0:
        return "long"
    if pos < 0:
        return "short"
    return "flat"


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _add_run_columns(frame: pd.DataFrame, source_start: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(_month_start(source_start))
    result["requested_start_month"] = source_start
    result["requested_end"] = ""
    return result


def _focus_inputs() -> tuple[list[str], pd.Timestamp, pd.Timestamp]:
    decision = json.loads(STAGE010_DECISION_PATH.read_text(encoding="utf-8"))
    focus_start = pd.Timestamp(decision["focus_start"]).normalize()
    focus_end = pd.Timestamp(decision["focus_end"]).normalize()
    focus = pd.read_csv(STAGE010_FOCUS_WINDOWS_PATH, encoding="utf-8-sig")
    sources = focus["source_start_month"].dropna().astype(str).drop_duplicates().tolist()
    return sorted(sources), focus_start, focus_end


def _run_focus_sources(sources: list[str], focus_end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s901.s513._metadata()
    curve_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []

    for idx, source in enumerate(sources, start=1):
        start = _month_start(source)
        print(f"[stage011] running {idx}/{len(sources)} source={source} end={_date_text(focus_end)}", flush=True)
        combined, frames, _spec = s901._run_live_c9(metadata, start, focus_end)

        curve = _add_run_columns(combined.copy(), source)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        if "drawdown_pct" not in curve.columns:
            curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
        if "broker10_margin_to_equity_pct" not in curve.columns:
            curve["broker10_margin_to_equity_pct"] = 0.0
        curve["requested_end"] = _date_text(focus_end)
        curve_frames.append(curve)

        positions = _add_run_columns(frames.get("positions", pd.DataFrame()).copy(), source)
        if not positions.empty:
            positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
            for column in [
                "start_pos",
                "end_pos",
                "pos_change",
                "close_price",
                "pre_close",
                "trade_count",
                "turnover",
                "commission",
                "slippage",
                "holding_pnl",
                "trading_pnl",
                "total_pnl",
                "net_pnl",
            ]:
                positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)
            positions["product"] = positions["vt_symbol"].map(_product_from_vt_symbol)
            positions["direction"] = positions.apply(
                lambda row: _direction_from_pos(float(row["start_pos"]), float(row["end_pos"])), axis=1
            )
            positions["requested_end"] = _date_text(focus_end)
            position_frames.append(positions)

            margin_daily, product_margin = s901.s513._position_margin(positions, metadata)
            margin_daily = _add_run_columns(margin_daily, source)
            product_margin = _add_run_columns(product_margin, source)
            margin_frames.append(margin_daily)
            product_margin_frames.append(product_margin)

    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    positions = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    margin = pd.concat(margin_frames, ignore_index=True, sort=False) if margin_frames else pd.DataFrame()
    product_margin = pd.concat(product_margin_frames, ignore_index=True, sort=False) if product_margin_frames else pd.DataFrame()
    return curves, positions, margin, product_margin


def _validation(curves: pd.DataFrame, positions: pd.DataFrame, focus_start: pd.Timestamp, focus_end: pd.Timestamp) -> pd.DataFrame:
    reference = pd.read_csv(REFERENCE_CURVES_PATH, encoding="utf-8-sig")
    reference["date"] = pd.to_datetime(reference["date"], errors="coerce").dt.normalize()
    reference["account_equity"] = pd.to_numeric(reference["account_equity"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for source, curve in curves.groupby("requested_start_month", sort=True):
        source = str(source)
        curve = curve.sort_values("date").copy()
        ref = reference[reference["requested_start_month"].astype(str).eq(source)].copy()
        pos = positions[positions["requested_start_month"].astype(str).eq(source)].copy()
        for date in (focus_start, focus_end):
            actual_row = curve[curve["date"].eq(date)]
            ref_row = ref[ref["date"].eq(date)]
            rows.append(
                {
                    "source_start_month": source,
                    "check_type": f"equity_at_{date.date().isoformat()}",
                    "actual": float(actual_row["account_equity"].iloc[0]) if not actual_row.empty else np.nan,
                    "reference": float(ref_row["account_equity"].iloc[0]) if not ref_row.empty else np.nan,
                    "abs_diff": (
                        abs(float(actual_row["account_equity"].iloc[0]) - float(ref_row["account_equity"].iloc[0]))
                        if not actual_row.empty and not ref_row.empty
                        else np.nan
                    ),
                }
            )

        window_curve = curve[curve["date"].gt(focus_start) & curve["date"].le(focus_end)].copy()
        window_pos = pos[pos["date"].gt(focus_start) & pos["date"].le(focus_end)].copy()
        curve_net = float(pd.to_numeric(window_curve["net_pnl"], errors="coerce").fillna(0.0).sum())
        pos_net = float(pd.to_numeric(window_pos["net_pnl"], errors="coerce").fillna(0.0).sum())
        rows.append(
            {
                "source_start_month": source,
                "check_type": "window_curve_net_pnl_vs_positions",
                "actual": curve_net,
                "reference": pos_net,
                "abs_diff": abs(curve_net - pos_net),
            }
        )
        start_equity = float(curve[curve["date"].eq(focus_start)]["account_equity"].iloc[0])
        end_equity = float(curve[curve["date"].eq(focus_end)]["account_equity"].iloc[0])
        rows.append(
            {
                "source_start_month": source,
                "check_type": "window_equity_change_vs_curve_net_pnl",
                "actual": end_equity - start_equity,
                "reference": curve_net,
                "abs_diff": abs((end_equity - start_equity) - curve_net),
            }
        )
    return pd.DataFrame(rows)


def _window_positions(positions: pd.DataFrame, focus_start: pd.Timestamp, focus_end: pd.Timestamp) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for source, source_positions in positions.groupby("requested_start_month", sort=True):
        source_positions = source_positions.copy()
        existing = set(
            source_positions[
                source_positions["date"].eq(focus_start) & pd.to_numeric(source_positions["end_pos"], errors="coerce").abs().gt(1e-9)
            ]["vt_symbol"].astype(str)
        )
        window = source_positions[source_positions["date"].gt(focus_start) & source_positions["date"].le(focus_end)].copy()
        if window.empty:
            continue
        active_or_traded = (
            window["start_pos"].abs()
            + window["end_pos"].abs()
            + window["pos_change"].abs()
            + window["trade_count"].abs()
        ) > 1e-9
        window = window[active_or_traded].copy()
        window["source_bucket"] = np.where(
            window["vt_symbol"].astype(str).isin(existing),
            "existing_at_focus_start",
            "opened_or_traded_after_focus_start",
        )
        window["broker10_margin_estimate"] = 0.0
        rows.append(window)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _summarize(window: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if window.empty:
        return pd.DataFrame()
    output = (
        window.groupby(keys, dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("date", "nunique"),
            source_count=("requested_start_month", "nunique"),
            max_abs_end_pos=("end_pos", lambda s: float(pd.to_numeric(s, errors="coerce").abs().max())),
        )
        .reset_index()
    )
    output["holding_share_of_net_pct"] = np.where(
        output["net_pnl"].abs().gt(1e-9),
        output["holding_pnl"] / output["net_pnl"] * 100.0,
        np.nan,
    )
    return output.sort_values("net_pnl").reset_index(drop=True)


def _daily_summary(window: pd.DataFrame, margin: pd.DataFrame, curves: pd.DataFrame) -> pd.DataFrame:
    if window.empty:
        return pd.DataFrame()
    daily = (
        window.groupby(["requested_start_month", "date"], dropna=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            trade_count=("trade_count", "sum"),
            active_contract_rows=("vt_symbol", "nunique"),
        )
        .reset_index()
    )
    margin_keep = margin[["requested_start_month", "date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]].copy()
    curve = curves.copy()
    if "drawdown_pct" not in curve.columns:
        curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    if "broker10_margin_to_equity_pct" not in curve.columns:
        curve["broker10_margin_to_equity_pct"] = 0.0
    curve_keep = curve[["requested_start_month", "date", "account_equity", "broker10_margin_to_equity_pct", "drawdown_pct"]].copy()
    daily = daily.merge(margin_keep, on=["requested_start_month", "date"], how="left").merge(
        curve_keep, on=["requested_start_month", "date"], how="left"
    )
    daily["broker10_margin_estimate"] = pd.to_numeric(daily["c3_margin_exact"], errors="coerce").fillna(0.0) * BROKER10_MULTIPLIER
    return daily.sort_values("net_pnl").reset_index(drop=True)


def _plot(daily: pd.DataFrame, bucket: pd.DataFrame, product: pd.DataFrame, validation: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)

    ax = axes[0, 0]
    if not daily.empty:
        by_date = daily.groupby("date", as_index=False).agg(net_pnl=("net_pnl", "sum"), holding_pnl=("holding_pnl", "sum"))
        ax.plot(by_date["date"], by_date["net_pnl"], label="net_pnl", color="#2563eb", linewidth=1.0)
        ax.plot(by_date["date"], by_date["holding_pnl"], label="holding_pnl", color="#dc2626", linewidth=1.0, alpha=0.8)
    ax.axhline(0, color="#111827", linestyle="--", linewidth=0.8)
    ax.set_title("Focus Window Daily PnL Across Sources")
    ax.set_ylabel("pnl")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")

    ax = axes[0, 1]
    if not bucket.empty:
        plot_bucket = bucket.sort_values("net_pnl")
        ax.barh(plot_bucket["source_bucket"], plot_bucket["net_pnl"], color=np.where(plot_bucket["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("PnL By Position Source Bucket")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 0]
    if not product.empty:
        prod = pd.concat([product.head(10), product.tail(5)]).drop_duplicates(["product", "direction", "source_bucket"]).copy()
        prod["label"] = prod["product"].astype(str) + " " + prod["direction"].astype(str) + "\n" + prod["source_bucket"].astype(str)
        ax.barh(prod["label"], prod["net_pnl"], color=np.where(prod["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax.set_title("Product/Direction Position PnL")
    ax.set_xlabel("net pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 1]
    if not validation.empty:
        check = validation.groupby("check_type", as_index=False).agg(max_abs_diff=("abs_diff", "max"))
        ax.barh(check["check_type"], check["max_abs_diff"], color="#7c3aed")
    ax.set_title("Validation Max Abs Diff")
    ax.set_xlabel("abs diff")
    ax.grid(True, axis="x", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    validation: pd.DataFrame,
    bucket: pd.DataFrame,
    product: pd.DataFrame,
    daily: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 焦点窗口持仓 PnL 归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读重跑与持仓归因；不改策略、不扫参数、不连接 CTP、不调用下单。",
        f"- 焦点窗口：`{decision['focus_start']}` 到 `{decision['focus_end']}`。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随长期收益来自右尾，不能用单一回撤窗口直接反推黑名单或缩手阈值。",
        "- PBO 框架要求先做路径归因和多窗口验证，再讨论账户层保护。",
        "",
        "## 一致性校验",
        "",
        _md_table(validation, max_rows=60),
        "",
        "## 持仓来源分桶",
        "",
        _md_table(bucket, max_rows=20),
        "",
        "## 品种方向归因",
        "",
        _md_table(product, max_rows=40),
        "",
        "## 最大亏损日",
        "",
        _md_table(daily.sort_values("net_pnl").head(30), max_rows=30),
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
    sources, focus_start, focus_end = _focus_inputs()
    curves, positions, margin, product_margin = _run_focus_sources(sources, focus_end)
    validation = _validation(curves, positions, focus_start, focus_end)
    window = _window_positions(positions, focus_start, focus_end)
    bucket = _summarize(window, ["source_bucket"])
    product = _summarize(window, ["product", "direction", "source_bucket"])
    daily = _daily_summary(window, margin, curves)
    _plot(daily, bucket, product, validation)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_DETAIL_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(SOURCE_BUCKET_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    margin.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")

    max_validation_diff = float(pd.to_numeric(validation["abs_diff"], errors="coerce").max()) if not validation.empty else np.nan
    source_losses = bucket.copy()
    source_losses["loss_abs"] = source_losses["net_pnl"].clip(upper=0.0).abs()
    total_loss = float(source_losses["loss_abs"].sum()) if not source_losses.empty else 0.0
    existing_loss = float(
        source_losses[source_losses["source_bucket"].eq("existing_at_focus_start")]["loss_abs"].sum()
    )
    after_start_loss = float(
        source_losses[source_losses["source_bucket"].eq("opened_or_traded_after_focus_start")]["loss_abs"].sum()
    )
    existing_share = existing_loss / total_loss * 100.0 if total_loss else 0.0
    after_start_share = after_start_loss / total_loss * 100.0 if total_loss else 0.0
    worst_product = product.iloc[0].to_dict() if not product.empty else {}
    worst_day = daily.iloc[0].to_dict() if not daily.empty else {}

    if max_validation_diff > 1e-6:
        decision_label = "stage011_validation_warning_do_not_use_for_strategy"
    elif existing_share >= 60.0:
        decision_label = "stage011_left_tail_dominated_by_existing_positions"
    elif after_start_share >= 60.0:
        decision_label = "stage011_left_tail_dominated_by_new_or_traded_positions"
    else:
        decision_label = "stage011_left_tail_mixed_existing_and_new_positions"

    core_attribution = (
        f"一致性最大差异 {max_validation_diff:.6f}；焦点窗口持仓净损失中，"
        f"窗口起点已有仓位亏损占比 {existing_share:.2f}%，窗口后新增/交易仓位亏损占比 {after_start_share:.2f}%。"
        f"最大品种方向拖累为 {worst_product.get('product', 'NA')} {worst_product.get('direction', 'NA')} "
        f"{worst_product.get('source_bucket', 'NA')}，net_pnl={float(worst_product.get('net_pnl', np.nan)):,.2f}；"
        f"最大亏损日为 {worst_day.get('date', 'NA')}，net_pnl={float(worst_day.get('net_pnl', np.nan)):,.2f}。"
    )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "focus_start": focus_start.date().isoformat(),
        "focus_end": focus_end.date().isoformat(),
        "source_count": int(len(sources)),
        "curve_rows": int(len(curves)),
        "position_rows": int(len(positions)),
        "window_position_rows": int(len(window)),
        "max_validation_abs_diff": max_validation_diff,
        "total_loss_abs": total_loss,
        "existing_at_focus_start_loss_abs": existing_loss,
        "opened_or_traded_after_focus_start_loss_abs": after_start_loss,
        "existing_at_focus_start_loss_share_pct": existing_share,
        "opened_or_traded_after_focus_start_loss_share_pct": after_start_share,
        "worst_product_direction": _json_safe(worst_product),
        "worst_day": _json_safe(worst_day),
        "decision": decision_label,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Use position-level path attribution before proposing account protection; do not fit a product or threshold rule "
            "to the single 2022-07/2023-07 left-tail."
        ),
        "overfit_reflection_before": (
            "否。Stage011 只补 positions 路径证据，不设计新规则、不选择参数。"
        ),
        "continue_value_before": (
            "是。Stage010 已证明 closed_lots 净额解释不了账户损失，必须拆 daily holding_pnl。"
        ),
        "core_attribution": core_attribution,
        "overfit_reflection_after": (
            "否。本阶段只做重跑一致性校验和持仓 PnL 分桶，没有把坏窗口反推成黑名单。"
        ),
        "continue_value_after": (
            "有。该归因能决定下一步应研究已有仓位降风险，还是新增开仓闸门；但仍需真实多窗口验证。"
        ),
        "outputs": {
            "curves": str(CURVES_PATH),
            "positions": str(POSITIONS_PATH),
            "window_detail": str(WINDOW_DETAIL_PATH),
            "source_bucket": str(SOURCE_BUCKET_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "daily_summary": str(DAILY_SUMMARY_PATH),
            "validation": str(VALIDATION_PATH),
            "margin_daily": str(MARGIN_DAILY_PATH),
            "product_margin": str(PRODUCT_MARGIN_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, validation, bucket, product, daily)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("source_bucket")
    print(bucket.to_string(index=False))
    print("product_direction")
    print(product.head(30).to_string(index=False))
    print("daily")
    print(daily.head(20).to_string(index=False))


if __name__ == "__main__":
    main()

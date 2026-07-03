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
STAGE = "Stage024"
MODEL_TAG = "stage024_stage022_base_position_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage024_stage022_base_position_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_stage022_base_position_attribution"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_stage013_base_holding_position_attribution"
STAGE006_PREFIX = "rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution"
STAGE006_TAG = "stage006_stage013_base_holding_position_attribution_v1"
POSITIONS_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_positions_{STAGE006_TAG}.csv.gz"

STAGE023_OUTPUT_DIR = LINE_DIR / "outputs" / "stage023_stage022_residual_window_attribution"
STAGE023_PREFIX = "rebuilt_c9_v2_stage023_stage022_residual_window_attribution"
STAGE023_TAG = "stage023_stage022_residual_window_attribution_v1"
FOCUS_WINDOWS_PATH = STAGE023_OUTPUT_DIR / f"{STAGE023_PREFIX}_focus_windows_{STAGE023_TAG}.csv"
STAGE023_WINDOW_ATTRIBUTION_PATH = STAGE023_OUTPUT_DIR / f"{STAGE023_PREFIX}_window_attribution_{STAGE023_TAG}.csv"
STAGE023_DECISION_PATH = STAGE023_OUTPUT_DIR / f"{STAGE023_PREFIX}_decision_{STAGE023_TAG}.json"

WINDOW_POSITION_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_position_detail_{MODEL_TAG}.csv.gz"
WINDOW_VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_validation_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
SOURCE_BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_bucket_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_loss_driver_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0629_stage024_stage022_base_position_attribution.md"


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


def _date_text(value: Any) -> str:
    return _date(value).date().isoformat()


def product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        product = "".join(ch for ch in text if ch.isalpha()) or text
        return product
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def prepare_positions(positions: pd.DataFrame) -> pd.DataFrame:
    data = positions.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["source_start_month"] = data["requested_start_month"]
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["requested_start_month", "date"])
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "total_pnl",
    ]:
        data[column] = _numeric(data, column)
    data["product"] = data["vt_symbol"].map(product_from_vt_symbol)
    position = data["start_pos"].where(data["start_pos"].abs().gt(1e-9), data["end_pos"])
    position = position.where(position.abs().gt(1e-9), np.sign(data["pos_change"]))
    data["direction"] = np.select([position.gt(0), position.lt(0)], ["long", "short"], default="flat")
    return data.sort_values(["requested_start_month", "date", "vt_symbol"]).reset_index(drop=True)


def _window_active_positions(
    positions: pd.DataFrame,
    window: pd.Series,
) -> pd.DataFrame:
    data = positions if {"product", "direction", "source_start_month"}.issubset(positions.columns) else prepare_positions(positions)
    source = str(window["source_start_month"])
    start = _date(window["start_date"])
    end = _date(window["end_date"])
    source_data = data[data["requested_start_month"].astype(str).eq(source)].copy()
    start_rows = source_data[source_data["date"].eq(start)]
    existing_contracts = set(
        start_rows[
            (
                start_rows["start_pos"].abs()
                + start_rows["end_pos"].abs()
                + start_rows["pos_change"].abs()
                + start_rows["trade_count"].abs()
            ).gt(1e-9)
        ]["vt_symbol"].astype(str)
    )
    segment = source_data[source_data["date"].gt(start) & source_data["date"].le(end)].copy()
    if segment.empty:
        return segment
    active = (
        segment["start_pos"].abs()
        + segment["end_pos"].abs()
        + segment["pos_change"].abs()
        + segment["trade_count"].abs()
        + segment["net_pnl"].abs()
    ).gt(1e-9)
    segment = segment[active].copy()
    if segment.empty:
        return segment
    segment["source_bucket"] = np.where(
        segment["vt_symbol"].astype(str).isin(existing_contracts),
        "existing_at_window_start",
        "opened_or_traded_after_window_start",
    )
    return segment


def attribute_window_positions(
    positions: pd.DataFrame,
    window: pd.Series,
    selected_rank: int,
) -> pd.DataFrame:
    segment = _window_active_positions(positions, window)
    if segment.empty:
        return pd.DataFrame()
    source = str(window["source_start_month"])
    start = _date(window["start_date"])
    end = _date(window["end_date"])
    segment["cost"] = segment["commission"] + segment["slippage"]
    grouped = (
        segment.groupby(["product", "direction", "source_bucket"], dropna=False)
        .agg(
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            cost=("cost", "sum"),
            net_pnl=("net_pnl", "sum"),
            active_days=("date", "nunique"),
            contract_count=("vt_symbol", "nunique"),
            trade_count=("trade_count", "sum"),
            max_abs_end_pos=("end_pos", lambda values: float(pd.to_numeric(values, errors="coerce").abs().max())),
        )
        .reset_index()
    )
    grouped["selected_rank"] = int(selected_rank)
    grouped["source_start_month"] = source
    grouped["window_start_date"] = _date_text(start)
    grouped["window_end_date"] = _date_text(end)
    grouped["window_id"] = f"{int(selected_rank):03d}_{source}_{_date_text(start)}_{_date_text(end)}"
    grouped["window_return_pct"] = float(window.get("return_pct", np.nan))
    ordered = [
        "selected_rank",
        "window_id",
        "source_start_month",
        "window_start_date",
        "window_end_date",
        "window_return_pct",
        "product",
        "direction",
        "source_bucket",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "cost",
        "net_pnl",
        "active_days",
        "contract_count",
        "trade_count",
        "max_abs_end_pos",
    ]
    return grouped[ordered].sort_values("net_pnl").reset_index(drop=True)


def build_window_position_detail(focus_windows: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    prepared = prepare_positions(positions)
    rows: list[pd.DataFrame] = []
    for rank, (_, window) in enumerate(focus_windows.iterrows(), start=1):
        detail = attribute_window_positions(prepared, window, selected_rank=rank)
        if not detail.empty:
            rows.append(detail)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_window_validation(
    focus_windows: pd.DataFrame,
    positions: pd.DataFrame,
    stage023_window_attribution: pd.DataFrame,
) -> pd.DataFrame:
    prepared = prepare_positions(positions)
    stage023 = stage023_window_attribution.copy()
    for column in ["start_date", "end_date"]:
        stage023[column] = pd.to_datetime(stage023[column], errors="coerce").dt.normalize()
    stage023["source_start_month"] = stage023["source_start_month"].astype(str)
    rows: list[dict[str, Any]] = []
    for rank, (_, window) in enumerate(focus_windows.iterrows(), start=1):
        source = str(window["source_start_month"])
        start = _date(window["start_date"])
        end = _date(window["end_date"])
        segment = _window_active_positions(prepared, window)
        position_net = float(segment["net_pnl"].sum()) if not segment.empty else 0.0
        position_holding = float(segment["holding_pnl"].sum()) if not segment.empty else 0.0
        position_trading = float(segment["trading_pnl"].sum()) if not segment.empty else 0.0
        position_cost = float((segment["commission"] + segment["slippage"]).sum()) if not segment.empty else 0.0
        matched = stage023[
            stage023["source_start_month"].eq(source)
            & stage023["start_date"].eq(start)
            & stage023["end_date"].eq(end)
        ]
        expected = float(matched.iloc[0]["base_net_pnl_in_window"]) if not matched.empty else np.nan
        rows.append(
            {
                "selected_rank": rank,
                "source_start_month": source,
                "start_date": _date_text(start),
                "end_date": _date_text(end),
                "return_pct": float(window.get("return_pct", np.nan)),
                "position_net_pnl": position_net,
                "position_holding_pnl": position_holding,
                "position_trading_pnl": position_trading,
                "position_cost": position_cost,
                "stage023_base_net_pnl_in_window": expected,
                "base_net_pnl_abs_diff": abs(position_net - expected) if np.isfinite(expected) else np.nan,
                "active_position_rows": int(len(segment)),
                "active_contract_count": int(segment["vt_symbol"].nunique()) if not segment.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def summarize_product_direction(window_position_detail: pd.DataFrame) -> pd.DataFrame:
    if window_position_detail.empty:
        return pd.DataFrame()
    summary = (
        window_position_detail.groupby(["product", "direction", "source_bucket"], dropna=False)
        .agg(
            affected_window_count=("window_id", "nunique"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            cost=("cost", "sum"),
            net_pnl=("net_pnl", "sum"),
            active_days=("active_days", "sum"),
            contract_count=("contract_count", "sum"),
            trade_count=("trade_count", "sum"),
            worst_window_return_pct=("window_return_pct", "min"),
            max_abs_end_pos=("max_abs_end_pos", "max"),
        )
        .reset_index()
        .sort_values(["net_pnl", "holding_pnl"], ascending=[True, True])
    )
    total_loss_abs = float(summary.loc[summary["net_pnl"].lt(0), "net_pnl"].abs().sum())
    summary["net_loss_share_pct"] = np.where(
        summary["net_pnl"].lt(0) & (total_loss_abs > 1e-12),
        summary["net_pnl"].abs() / total_loss_abs * 100.0,
        0.0,
    )
    return summary


def summarize_source_bucket(window_position_detail: pd.DataFrame) -> pd.DataFrame:
    if window_position_detail.empty:
        return pd.DataFrame()
    summary = (
        window_position_detail.groupby(["source_bucket"], dropna=False)
        .agg(
            affected_window_count=("window_id", "nunique"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            cost=("cost", "sum"),
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
        )
        .reset_index()
        .sort_values("net_pnl")
    )
    loss_abs = float(summary.loc[summary["net_pnl"].lt(0), "net_pnl"].abs().sum())
    summary["net_loss_share_pct"] = np.where(
        summary["net_pnl"].lt(0) & (loss_abs > 1e-12),
        summary["net_pnl"].abs() / loss_abs * 100.0,
        0.0,
    )
    return summary


def summarize_source(window_validation: pd.DataFrame) -> pd.DataFrame:
    if window_validation.empty:
        return pd.DataFrame()
    return (
        window_validation.groupby("source_start_month", dropna=False)
        .agg(
            window_count=("source_start_month", "size"),
            worst_return_pct=("return_pct", "min"),
            position_net_pnl=("position_net_pnl", "sum"),
            position_holding_pnl=("position_holding_pnl", "sum"),
            position_trading_pnl=("position_trading_pnl", "sum"),
            position_cost=("position_cost", "sum"),
            max_base_net_pnl_abs_diff=("base_net_pnl_abs_diff", "max"),
            active_position_rows=("active_position_rows", "sum"),
            active_contract_count=("active_contract_count", "sum"),
        )
        .reset_index()
        .sort_values("worst_return_pct")
    )


def plot_loss_driver_chart(product_direction_summary: pd.DataFrame, path: Path) -> None:
    if product_direction_summary.empty:
        return
    data = product_direction_summary.head(12).copy()
    data["label"] = data["product"].astype(str) + " " + data["direction"].astype(str) + " " + data["source_bucket"].astype(str)
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.barh(data["label"], data["net_pnl"], color=np.where(data["net_pnl"].lt(0), "#b23b3b", "#2f7d59"))
    ax.axvline(0.0, color="black", linewidth=0.8)
    ax.set_title("Stage024 Stage022 residual base position drivers")
    ax.set_xlabel("Net PnL across focus windows")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_report(
    decision: dict[str, Any],
    source_bucket_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
) -> str:
    lines = [
        "# Stage024 Stage022 base residual 持仓归因",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- focus windows：`{decision['focus_window_count']}`",
        f"- position net pnl：`{decision['focus_position_net_pnl']:.4f}`",
        f"- position holding pnl：`{decision['focus_position_holding_pnl']:.4f}`",
        f"- position trading pnl：`{decision['focus_position_trading_pnl']:.4f}`",
        f"- position cost：`{decision['focus_position_cost']:.4f}`",
        f"- max validation diff：`{decision['max_base_net_pnl_abs_diff']:.8f}`",
        "",
        "## Source Bucket",
        "",
        _md_table(source_bucket_summary, 20),
        "",
        "## Product Direction",
        "",
        _md_table(product_direction_summary, 20),
        "",
        "## Source Summary",
        "",
        _md_table(source_summary, 20),
        "",
    ]
    return "\n".join(lines)


def write_stage_record(
    decision: dict[str, Any],
    source_bucket_summary: pd.DataFrame,
    product_direction_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    lines = [
        "# Stage024 Stage022 base residual 持仓归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{timestamp}",
        "- 阶段性质：只读归因；不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否；本阶段只定位剩余亏损持仓路径，不生成可上线规则",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：pyfolio drawdown period 分析、position-level performance attribution、Rob Carver/系统化期货分散与风险暴露管理思路。",
        "- 我的判断：Stage023 已确认 Stage022 delta 整体在减亏；继续推进前必须把 base residual 拆到持仓层，避免把趋势系统正常回撤误改成单品种/单日期黑名单。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage024_stage022_base_position_attribution.py`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage024_stage022_base_position_attribution.py`",
        "- 新增参数：无",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 输入窗口：Stage023 focus windows。",
        "- 输入持仓：Stage006 已保存 Stage013 base positions。",
        "- 口径：窗口内 `(start_date, end_date]` 活跃持仓的 holding/trading/cost/net PnL；按起点日是否已有仓分桶。",
        "- 校验：窗口持仓净 PnL 必须对齐 Stage023 `base_net_pnl_in_window`。",
        "",
        "## 结果",
        "",
        f"- focus windows：`{decision['focus_window_count']}`",
        f"- focus position net pnl：`{decision['focus_position_net_pnl']:.4f}`",
        f"- focus position holding pnl：`{decision['focus_position_holding_pnl']:.4f}`",
        f"- focus position trading pnl：`{decision['focus_position_trading_pnl']:.4f}`",
        f"- focus position cost：`{decision['focus_position_cost']:.4f}`",
        f"- existing bucket net pnl：`{decision['existing_bucket_net_pnl']:.4f}`",
        f"- opened/traded bucket net pnl：`{decision['opened_bucket_net_pnl']:.4f}`",
        f"- top loss driver：`{decision['top_loss_driver']}`",
        f"- max base net pnl abs diff：`{decision['max_base_net_pnl_abs_diff']:.8f}`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## Source Bucket 汇总",
        "",
        _md_table(source_bucket_summary, 20),
        "",
        "## Product Direction 汇总",
        "",
        _md_table(product_direction_summary, 20),
        "",
        "## Source 汇总",
        "",
        _md_table(source_summary, 20),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只做已冻结 Stage022 focus 窗口的持仓归因，不根据结果改产品、方向、日期或阈值。",
        "- 运行后判断：否。结果可以提示下一步信号形状，但不能把 top loss driver 直接做黑名单；那会过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。若 base residual 仍集中在窗口后新增仓，下一步才值得继续找 PIT 入场确认或账户外层；若只是已有趋势仓正常回撤，则不该强行优化。",
        f"- 运行后判断：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
        f"- window_position_detail：`{WINDOW_POSITION_DETAIL_PATH}`",
        f"- window_validation：`{WINDOW_VALIDATION_PATH}`",
        f"- product_direction_summary：`{PRODUCT_DIRECTION_SUMMARY_PATH}`",
        f"- source_bucket_summary：`{SOURCE_BUCKET_SUMMARY_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
    ]
    return "\n".join(lines)


def run_stage() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    focus_windows = _read_csv(FOCUS_WINDOWS_PATH)
    stage023_window_attribution = _read_csv(STAGE023_WINDOW_ATTRIBUTION_PATH)
    positions = _read_csv(POSITIONS_PATH)

    window_position_detail = build_window_position_detail(focus_windows, positions)
    window_validation = build_window_validation(focus_windows, positions, stage023_window_attribution)
    product_direction_summary = summarize_product_direction(window_position_detail)
    source_bucket_summary = summarize_source_bucket(window_position_detail)
    source_summary = summarize_source(window_validation)

    focus_position_net = float(window_validation["position_net_pnl"].sum())
    focus_position_holding = float(window_validation["position_holding_pnl"].sum())
    focus_position_trading = float(window_validation["position_trading_pnl"].sum())
    focus_position_cost = float(window_validation["position_cost"].sum())
    max_diff = float(window_validation["base_net_pnl_abs_diff"].max())
    existing_bucket = source_bucket_summary[source_bucket_summary["source_bucket"].eq("existing_at_window_start")]
    opened_bucket = source_bucket_summary[source_bucket_summary["source_bucket"].eq("opened_or_traded_after_window_start")]
    existing_net = float(existing_bucket["net_pnl"].sum()) if not existing_bucket.empty else 0.0
    opened_net = float(opened_bucket["net_pnl"].sum()) if not opened_bucket.empty else 0.0
    top_row = product_direction_summary.iloc[0] if not product_direction_summary.empty else pd.Series(dtype=object)
    top_loss_driver = (
        f"{top_row.get('product')} {top_row.get('direction')} {top_row.get('source_bucket')} net={float(top_row.get('net_pnl', 0.0)):.4f}"
        if not product_direction_summary.empty
        else "none"
    )
    if abs(opened_net) > abs(existing_net):
        decision_label = "stage024_base_residual_opened_positions_dominate_need_pit_entry_signal"
        continue_value_after = "有价值。剩余 base 亏损主要来自窗口后新增/交易仓，下一步应围绕新增仓的 PIT 入场状态、账户状态或外生确认继续找结构信号。"
    else:
        decision_label = "stage024_base_residual_existing_positions_dominate_need_account_layer"
        continue_value_after = "有价值但方向应偏账户外层。剩余 base 亏损主要来自窗口起点已有仓，继续调入场信号可能作用有限，应优先看账户层或持仓层风险暴露。"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "focus_window_count": int(len(focus_windows)),
        "focus_position_net_pnl": focus_position_net,
        "focus_position_holding_pnl": focus_position_holding,
        "focus_position_trading_pnl": focus_position_trading,
        "focus_position_cost": focus_position_cost,
        "existing_bucket_net_pnl": existing_net,
        "opened_bucket_net_pnl": opened_net,
        "top_loss_driver": top_loss_driver,
        "max_base_net_pnl_abs_diff": max_diff,
        "decision": decision_label,
        "external_research_judgment": (
            "Position-level drawdown attribution is needed before changing a trend-following system; "
            "otherwise a normal trend drawdown can be mistaken for a parameter bug."
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
            "stage023_decision": str(STAGE023_DECISION_PATH),
            "focus_windows": str(FOCUS_WINDOWS_PATH),
            "stage023_window_attribution": str(STAGE023_WINDOW_ATTRIBUTION_PATH),
            "positions": str(POSITIONS_PATH),
        },
        "outputs": {
            "window_position_detail": str(WINDOW_POSITION_DETAIL_PATH),
            "window_validation": str(WINDOW_VALIDATION_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "source_bucket_summary": str(SOURCE_BUCKET_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }

    window_position_detail.to_csv(WINDOW_POSITION_DETAIL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    window_validation.to_csv(WINDOW_VALIDATION_PATH, index=False, encoding="utf-8-sig")
    product_direction_summary.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_bucket_summary.to_csv(SOURCE_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    plot_loss_driver_chart(product_direction_summary, CHART_PATH)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        write_report(decision, source_bucket_summary, product_direction_summary, source_summary),
        encoding="utf-8",
    )
    STAGE_RECORD_PATH.write_text(
        write_stage_record(decision, source_bucket_summary, product_direction_summary, source_summary),
        encoding="utf-8",
    )
    return decision


if __name__ == "__main__":
    result = run_stage()
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2))

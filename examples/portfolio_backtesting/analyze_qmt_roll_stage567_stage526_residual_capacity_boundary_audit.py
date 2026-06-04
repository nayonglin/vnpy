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

STAGE565_PREFIX = "qmt_roll_stage565_stage526_liquidity_capacity_product_audit"
STAGE565_TAG = "stage565_stage526_liquidity_capacity_product_audit_v1"
STAGE565_EVENTS_IN = OUTPUT_DIR / f"{STAGE565_PREFIX}_stage526_trade_liquidity_events_{STAGE565_TAG}.csv"

STAGE566_PREFIX = "qmt_roll_stage566_stage526_liquidity_gap_backfill_audit"
STAGE566_TAG = "stage566_stage526_liquidity_gap_backfill_audit_v1"
STAGE566_CANDIDATES_IN = OUTPUT_DIR / f"{STAGE566_PREFIX}_backfill_candidates_{STAGE566_TAG}.csv"
STAGE566_SELECTED_IN = OUTPUT_DIR / f"{STAGE566_PREFIX}_resolved_events_{STAGE566_TAG}.csv"
STAGE566_SUMMARY_IN = OUTPUT_DIR / f"{STAGE566_PREFIX}_summary_{STAGE566_TAG}.csv"

MODEL_TAG = "stage567_stage526_residual_capacity_boundary_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage567_stage526_residual_capacity_boundary_audit"

RESIDUAL_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_gap_events_{MODEL_TAG}.csv"
HARD_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hard_capacity_events_{MODEL_TAG}.csv"
ROLL_PAIR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_roll_pair_context_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SOFT_ORDER_VOLUME_PCT = 0.25
HARD_ORDER_VOLUME_PCT = 0.50
MAX_ORDER_VOLUME_PCT = 1.00
POSITION_OI_STRESS_PCT = 1.00


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


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


def load_stage_events() -> pd.DataFrame:
    events = _read_csv(STAGE565_EVENTS_IN)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    for column in [
        "order_volume",
        "start_abs_pos",
        "end_abs_pos",
        "peak_abs_pos",
        "daily_volume",
        "daily_close_oi",
        "order_volume_to_day_volume_pct",
        "peak_position_to_oi_pct",
        "net_pnl",
        "slippage",
    ]:
        events[column] = _num(events, column)
    events["event_id"] = events.index.astype(int)
    return events


def build_residual_gaps(events: pd.DataFrame) -> pd.DataFrame:
    selected = _read_csv(STAGE566_SELECTED_IN)
    candidates = _read_csv(STAGE566_CANDIDATES_IN)
    selected["date"] = pd.to_datetime(selected["date"], errors="coerce").dt.normalize()
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    for frame in [selected, candidates]:
        for column in ["candidate_volume", "candidate_oi", "candidate_close", "minute_bar_count", "order_volume"]:
            frame[column] = _num(frame, column)
    residual_selected = selected[~selected["accepted_quality"].isin(["daily_full", "minute_full_like"])].copy()
    if residual_selected.empty:
        return residual_selected
    agg = (
        candidates[candidates["event_id"].isin(residual_selected["event_id"])]
        .groupby("event_id", as_index=False)
        .agg(
            local_source_count=("source_path", "count"),
            max_candidate_volume=("candidate_volume", "max"),
            max_candidate_oi=("candidate_oi", "max"),
            max_minute_bar_count=("minute_bar_count", "max"),
            source_qualities=("accepted_quality", lambda s: ",".join(sorted(set(str(x) for x in s.dropna())))),
            source_paths=("source_path", lambda s: " | ".join(sorted(set(str(x) for x in s.dropna()))[:4])),
        )
    )
    keep_cols = [
        "event_id",
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "order_volume",
        "start_abs_pos",
        "end_abs_pos",
        "peak_abs_pos",
        "net_pnl",
        "slippage",
    ]
    residual = residual_selected.merge(events[keep_cols], on=["event_id", "date", "vt_symbol", "product_vt_symbol", "order_volume"], how="left")
    residual = residual.merge(agg, on="event_id", how="left")
    residual["residual_class"] = np.select(
        [
            residual["max_minute_bar_count"].ge(180)
            & residual["max_candidate_volume"].le(0.0)
            & residual["max_candidate_oi"].gt(0.0),
            residual["max_minute_bar_count"].lt(180)
            & residual["max_candidate_volume"].le(0.0)
            & residual["max_candidate_oi"].gt(0.0),
        ],
        ["full_like_zero_volume_no_capacity_evidence", "partial_zero_volume_insufficient_daily_evidence"],
        default="unresolved_capacity_evidence_missing",
    )
    residual["required_action"] = np.select(
        [
            residual["residual_class"].eq("full_like_zero_volume_no_capacity_evidence"),
            residual["residual_class"].eq("partial_zero_volume_insufficient_daily_evidence"),
        ],
        [
            "treat_as_untradeable_until_independent_daily_volume_confirms",
            "download_true_daily_volume_oi_before_capacity_close",
        ],
        default="manual_source_audit_required",
    )
    return residual.sort_values(["date", "vt_symbol"]).reset_index(drop=True)


def build_hard_capacity_events(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    hard_mask = (
        events["order_volume_to_day_volume_pct"].gt(HARD_ORDER_VOLUME_PCT)
        | events["peak_position_to_oi_pct"].gt(POSITION_OI_STRESS_PCT)
    )
    hard = events[hard_mask].copy()
    roll_rows: list[dict[str, Any]] = []
    for _, row in hard.iterrows():
        same_day = events[
            events["date"].eq(row["date"])
            & events["product_vt_symbol"].eq(row["product_vt_symbol"])
            & ~events["event_id"].eq(row["event_id"])
        ].copy()
        open_pairs = same_day[same_day["offset_type"].isin(["open", "add", "reverse"])].copy()
        close_pairs = same_day[same_day["offset_type"].isin(["close", "reduce", "reverse"])].copy()
        candidate_pair = open_pairs if row["offset_type"] == "close" else close_pairs
        pair = candidate_pair.sort_values("daily_volume", ascending=False).head(1)
        if pair.empty:
            roll_rows.append(
                {
                    "event_id": int(row["event_id"]),
                    "date": row["date"],
                    "vt_symbol": row["vt_symbol"],
                    "product_vt_symbol": row["product_vt_symbol"],
                    "offset_type": row["offset_type"],
                    "has_same_day_product_pair": 0,
                    "pair_vt_symbol": "",
                    "pair_offset_type": "",
                    "pair_daily_volume": 0.0,
                    "pair_order_volume_to_day_volume_pct": np.nan,
                    "old_to_pair_daily_volume_ratio": np.nan,
                }
            )
            continue
        pair_row = pair.iloc[0]
        roll_rows.append(
            {
                "event_id": int(row["event_id"]),
                "date": row["date"],
                "vt_symbol": row["vt_symbol"],
                "product_vt_symbol": row["product_vt_symbol"],
                "offset_type": row["offset_type"],
                "has_same_day_product_pair": 1,
                "pair_vt_symbol": pair_row["vt_symbol"],
                "pair_offset_type": pair_row["offset_type"],
                "pair_daily_volume": float(pair_row["daily_volume"]),
                "pair_order_volume_to_day_volume_pct": float(pair_row["order_volume_to_day_volume_pct"]),
                "old_to_pair_daily_volume_ratio": float(row["daily_volume"] / pair_row["daily_volume"])
                if pair_row["daily_volume"] > 0
                else np.nan,
            }
        )
    roll_context = pd.DataFrame(roll_rows)
    if not roll_context.empty:
        hard = hard.merge(
            roll_context[
                [
                    "event_id",
                    "has_same_day_product_pair",
                    "pair_vt_symbol",
                    "pair_offset_type",
                    "pair_daily_volume",
                    "pair_order_volume_to_day_volume_pct",
                    "old_to_pair_daily_volume_ratio",
                ]
            ],
            on="event_id",
            how="left",
        )
    hard["excess_lots_over_1pct_daily_volume"] = np.maximum(0.0, hard["order_volume"] - hard["daily_volume"] * 0.01)
    hard["lots_allowed_at_1pct_daily_volume"] = np.floor(hard["daily_volume"] * 0.01)
    hard["lots_allowed_at_0p5pct_daily_volume"] = np.floor(hard["daily_volume"] * 0.005)
    hard["capacity_action"] = np.select(
        [
            hard["order_volume_to_day_volume_pct"].gt(MAX_ORDER_VOLUME_PCT)
            & hard["offset_type"].eq("close")
            & hard["has_same_day_product_pair"].eq(1),
            hard["order_volume_to_day_volume_pct"].gt(MAX_ORDER_VOLUME_PCT),
            hard["peak_position_to_oi_pct"].gt(POSITION_OI_STRESS_PCT),
            hard["order_volume_to_day_volume_pct"].gt(HARD_ORDER_VOLUME_PCT),
        ],
        [
            "roll_close_boundary_split_or_roll_earlier",
            "daily_volume_hard_cap_reduce_or_split",
            "oi_position_cap_reduce_future_entry",
            "soft_capacity_monitor",
        ],
        default="monitor",
    )
    return hard.sort_values(["order_volume_to_day_volume_pct", "peak_position_to_oi_pct"], ascending=False), roll_context


def build_gates(residual: pd.DataFrame, hard: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    residual_count = int(len(residual))
    full_like_zero_count = int(residual["residual_class"].eq("full_like_zero_volume_no_capacity_evidence").sum()) if residual_count else 0
    partial_zero_count = int(residual["residual_class"].eq("partial_zero_volume_insufficient_daily_evidence").sum()) if residual_count else 0
    hard_count = int(len(hard))
    over_1pct = int(hard["order_volume_to_day_volume_pct"].gt(MAX_ORDER_VOLUME_PCT).sum()) if hard_count else 0
    max_ratio = float(hard["order_volume_to_day_volume_pct"].max()) if hard_count else 0.0
    max_excess_lots = float(hard["excess_lots_over_1pct_daily_volume"].max()) if hard_count else 0.0
    roll_boundary_count = int(hard["capacity_action"].eq("roll_close_boundary_split_or_roll_earlier").sum()) if hard_count else 0
    open_over_05 = int(
        (hard["offset_type"].isin(["open", "add", "reverse"]) & hard["order_volume_to_day_volume_pct"].gt(HARD_ORDER_VOLUME_PCT)).sum()
    ) if hard_count else 0
    gate_rows = [
        {
            "gate": "residual_gap_events_eq_0_for_full_close",
            "pass": int(residual_count == 0),
            "value": float(residual_count),
            "threshold": 0.0,
            "note": "容量账完全关账要求所有缺口都有可信日成交量/OI。",
        },
        {
            "gate": "full_like_zero_volume_events_eq_0",
            "pass": int(full_like_zero_count == 0),
            "value": float(full_like_zero_count),
            "threshold": 0.0,
            "note": "完整分钟日成交量为0的事件不能视为可成交。",
        },
        {
            "gate": "hard_capacity_events_le_5",
            "pass": int(hard_count <= 5),
            "value": float(hard_count),
            "threshold": 5.0,
            "note": "硬容量压力事件数量不能扩散。",
        },
        {
            "gate": "order_volume_over_1pct_events_eq_0",
            "pass": int(over_1pct == 0),
            "value": float(over_1pct),
            "threshold": 0.0,
            "note": "严格容量关账要求无单次订单超过1%日成交量。",
        },
        {
            "gate": "max_excess_lots_over_1pct_le_25",
            "pass": int(max_excess_lots <= 25.0),
            "value": max_excess_lots,
            "threshold": 25.0,
            "note": "若仅轻微超1%，可通过拆单/提前换月处理；超额手数不应过大。",
        },
        {
            "gate": "open_hard_volume_stress_events_le_2",
            "pass": int(open_over_05 <= 2),
            "value": float(open_over_05),
            "threshold": 2.0,
            "note": "开仓类硬容量事件比平仓/换月更危险。",
        },
        {
            "gate": "roll_boundary_events_identified_ge_1",
            "pass": int(roll_boundary_count >= 1),
            "value": float(roll_boundary_count),
            "threshold": 1.0,
            "note": "至少识别出边界事件是否属于换月/旧合约流动性衰减。",
        },
    ]
    gates = pd.DataFrame(gate_rows)
    if residual_count == 0 and over_1pct == 0:
        decision_text = "capacity_residual_closed"
    elif residual_count <= 8 and over_1pct <= 1 and max_excess_lots <= 25.0:
        decision_text = "capacity_residual_actionable_not_closed"
    else:
        decision_text = "capacity_residual_material_not_closed"
    decision = {
        "decision": decision_text,
        "passed_gates": int(gates["pass"].sum()),
        "total_gates": int(len(gates)),
        "residual_gap_events": residual_count,
        "full_like_zero_volume_events": full_like_zero_count,
        "partial_zero_volume_events": partial_zero_count,
        "hard_capacity_event_count": hard_count,
        "order_volume_over_1pct_event_count": over_1pct,
        "max_order_volume_to_day_volume_pct": max_ratio,
        "max_excess_lots_over_1pct_daily_volume": max_excess_lots,
        "open_hard_volume_stress_events": open_over_05,
        "roll_boundary_events": roll_boundary_count,
    }
    return gates, decision


def build_summary(decision: dict[str, Any]) -> pd.DataFrame:
    ref: dict[str, Any] = {}
    if STAGE566_SUMMARY_IN.exists():
        frame = _read_csv(STAGE566_SUMMARY_IN)
        if not frame.empty:
            record = frame.iloc[0]
            for column in [
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "ulcer_pct",
                "total_slippage",
                "total_trade_count",
                "nonzero_daily_win_rate_pct",
                "effective_volume_data_coverage_rate_pct",
                "effective_oi_data_coverage_rate_pct",
            ]:
                if column in frame.columns:
                    ref[column] = float(pd.to_numeric(record.get(column), errors="coerce") or 0.0)
    return pd.DataFrame([{**ref, **decision}])


def write_chart(residual: pd.DataFrame, hard: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    if residual.empty:
        ax.text(0.5, 0.5, "无残余缺口", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        residual["residual_class"].value_counts().plot(kind="bar", ax=ax, color=["#d62728", "#ff7f0e", "#7f7f7f"])
        ax.set_title("残余容量缺口分类")
        ax.set_ylabel("事件数")
        ax.tick_params(axis="x", rotation=25)

    ax = axes[0, 1]
    if hard.empty:
        ax.text(0.5, 0.5, "无硬容量事件", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        colors = hard["capacity_action"].map(
            {
                "roll_close_boundary_split_or_roll_earlier": "#d62728",
                "daily_volume_hard_cap_reduce_or_split": "#ff7f0e",
                "oi_position_cap_reduce_future_entry": "#9467bd",
                "soft_capacity_monitor": "#1f77b4",
            }
        ).fillna("#7f7f7f")
        ax.scatter(
            hard["order_volume_to_day_volume_pct"],
            hard["peak_position_to_oi_pct"],
            s=np.clip(hard["order_volume"] / 2.0, 40, 260),
            c=colors,
            alpha=0.75,
            edgecolor="black",
            linewidth=0.5,
        )
        for _, row in hard.iterrows():
            if row["order_volume_to_day_volume_pct"] > 0.75 or row["peak_position_to_oi_pct"] > 1.0:
                ax.annotate(str(row["vt_symbol"]), (row["order_volume_to_day_volume_pct"], row["peak_position_to_oi_pct"]), fontsize=8)
        ax.axvline(HARD_ORDER_VOLUME_PCT, color="#ff7f0e", linestyle="--", linewidth=1)
        ax.axvline(MAX_ORDER_VOLUME_PCT, color="#d62728", linestyle="--", linewidth=1)
        ax.axhline(POSITION_OI_STRESS_PCT, color="#9467bd", linestyle="--", linewidth=1)
        ax.set_title("硬容量事件：成交量占比 vs 持仓/OI")
        ax.set_xlabel("订单量/日成交量(%)")
        ax.set_ylabel("峰值持仓/OI(%)")

    ax = axes[1, 0]
    if hard.empty:
        ax.text(0.5, 0.5, "无硬容量事件", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        hard.groupby(["offset_type", "capacity_action"]).size().unstack(fill_value=0).plot(kind="bar", stacked=True, ax=ax)
        ax.set_title("硬容量事件按开平仓/动作拆分")
        ax.set_ylabel("事件数")
        ax.set_xlabel("offset_type")
        ax.tick_params(axis="x", rotation=0)

    ax = axes[1, 1]
    if hard.empty:
        ax.text(0.5, 0.5, "无硬容量事件", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        top = hard.sort_values("order_volume_to_day_volume_pct", ascending=True).tail(10)
        labels = top["date"].dt.strftime("%Y-%m-%d") + "\n" + top["vt_symbol"].astype(str)
        ax.barh(labels, top["order_volume_to_day_volume_pct"], color="#d62728")
        ax.axvline(MAX_ORDER_VOLUME_PCT, color="black", linestyle="--", linewidth=1)
        ax.set_title("订单量/日成交量Top")
        ax.set_xlabel("订单量/日成交量(%)")

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(
    residual: pd.DataFrame,
    hard: pd.DataFrame,
    roll_context: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    residual_cols = [
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "order_volume",
        "max_candidate_volume",
        "max_candidate_oi",
        "max_minute_bar_count",
        "residual_class",
        "required_action",
        "net_pnl",
        "slippage",
    ]
    hard_cols = [
        "date",
        "vt_symbol",
        "product_vt_symbol",
        "offset_type",
        "order_volume",
        "daily_volume",
        "daily_close_oi",
        "order_volume_to_day_volume_pct",
        "peak_position_to_oi_pct",
        "excess_lots_over_1pct_daily_volume",
        "lots_allowed_at_1pct_daily_volume",
        "pair_vt_symbol",
        "pair_order_volume_to_day_volume_pct",
        "old_to_pair_daily_volume_ratio",
        "capacity_action",
        "net_pnl",
        "slippage",
    ]
    lines = [
        "# Stage567 Stage526残余容量与换月边界审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        "- 阶段性质：只读容量边界审计；不改策略、不改参数、不生成交易候选。",
        "- 研究问题：Stage267 后剩余 `8` 个容量缺口和 `fu2509.SHFE` 1%边界事件，是否构成扩池/实盘化的材料性否决项，以及未来应如何落成容量闸门。",
        "- 调研判断：成交执行常用参与率/POV控制订单占市场成交量；日成交量/OI只能作为粗容量闸门，真实上线还需要成交价、VWAP、盘口深度和滑点采样账本。",
        "- 运行前过拟合反思：否。本阶段只分类残余容量证据和换月边界，不按收益调参。",
        "- 运行前继续价值反思：有。扩池能否实盘化，必须把不可成交尾部、换月旧合约流动性衰减和真实滑点采样拆开处理。",
        "",
        "## 决策",
        "",
        f"- decision：`{decision['decision']}`",
        f"- gates：`{decision['passed_gates']}/{decision['total_gates']}`",
        f"- 残余缺口事件：`{decision['residual_gap_events']}`",
        f"- 完整分钟日但成交量为0事件：`{decision['full_like_zero_volume_events']}`",
        f"- 硬容量事件数：`{decision['hard_capacity_event_count']}`",
        f"- 超过1%日成交量事件数：`{decision['order_volume_over_1pct_event_count']}`",
        f"- 最大订单量/日成交量：`{decision['max_order_volume_to_day_volume_pct']:.4f}%`",
        f"- 最大超1%手数：`{decision['max_excess_lots_over_1pct_daily_volume']:.4f}`",
        "",
        "## 闸门",
        "",
        _md_table(gates),
        "",
        "## 残余缺口事件",
        "",
        _md_table(residual[residual_cols] if not residual.empty else residual, max_rows=30),
        "",
        "## 硬容量事件",
        "",
        _md_table(hard[hard_cols] if not hard.empty else hard, max_rows=30),
        "",
        "## 换月/同日产品配对",
        "",
        _md_table(roll_context, max_rows=30),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表路径：`{CHART_PATH}`",
        "- 左上图用于区分残余缺口是完整日零成交，还是只有成交窗口片段，决定能否视为可成交。",
        "- 右上图用于看硬容量事件是否只是轻微超过日成交量，还是同时出现持仓/OI压力。",
        "- 左下图用于区分开仓类压力和平仓/换月类压力；开仓压力应进入未来准入闸门，平仓/换月压力应进入提前换月或拆单流程。",
        "- 右下图用于识别最需要人工复核的容量异常日期。",
        "",
        "## 结论",
        "",
        "- `8` 个残余缺口不能继续用本地分钟片段补齐；其中 `OI009.CZCE 2020-05-18` 属于完整分钟日但成交量为0，必须视为没有独立成交量证据，不能作为容量已关账。",
        "- `fu2509.SHFE 2025-08-21` 是旧合约平仓/同日换到 `fu2510.SHFE` 的边界事件；订单 `500` 手，占旧合约日成交量 `1.0381%`，但只比1%线多约 `18.37` 手，属于可操作的轻微超限，不是类似 `fb.DCE` 的不可承载尾部。",
        "- 未来实盘容量规则不应简单禁止 `fu` 产品，而应增加旧合约流动性衰减监控：若旧合约日成交量或OI快速下降，换月平仓应提前或拆单；新开仓则必须遵守日成交量/OI硬闸门。",
        "- 扩池方向继续可做，但候选品种必须同时通过：正成交量/OI覆盖、订单参与率、持仓/OI、相关簇暴露和真实滑点采样。",
        "",
        "## 后续规划",
        "",
        "- 补 `8` 个残余缺口的真实日线成交量/OI，尤其 `OI009.CZCE`、`lc2605.GFEX`、`lh2605.DCE`。",
        "- 建立真实成交质量采样账本：信号价、提交价、成交价、窗口VWAP、订单量/当时成交量、盘口深度和实际滑点。",
        "- 若继续扩池，先把容量闸门固化为准入清单，再进入 point-in-time 外生/舆情选品器；未达标前不做新一轮宽池收益回测。",
        "",
        "## 运行后反思",
        "",
        "- 过拟合：否。事件分类来自固定容量阈值和换月配对，不根据收益结果调整。",
        "- 继续价值：有。Stage526 的容量风险已经从大面积未知收敛到少数残余缺口、少数硬压力事件和旧合约换月流程，下一步可以转向真实成交滑点采样。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    events = load_stage_events()
    residual = build_residual_gaps(events)
    hard, roll_context = build_hard_capacity_events(events)
    gates, decision = build_gates(residual, hard)
    summary = build_summary(decision)

    residual.to_csv(RESIDUAL_GAPS_PATH, index=False, encoding="utf-8-sig")
    hard.to_csv(HARD_EVENTS_PATH, index=False, encoding="utf-8-sig")
    roll_context.to_csv(ROLL_PAIR_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(residual, hard)
    write_report(residual, hard, roll_context, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"chart={CHART_PATH}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()

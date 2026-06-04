from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage575_stage526_live_execution_p0_watchlist_v1"
OUTPUT_PREFIX = "qmt_roll_stage575_stage526_live_execution_p0_watchlist"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE573_DETAIL = OUTPUT_DIR / (
    "qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_"
    "hard_event_detail_stage573_stage526_hard_capacity_residual_evidence_audit_v1.csv"
)
STAGE568_TEMPLATE = OUTPUT_DIR / (
    "qmt_roll_stage568_stage526_execution_quality_ledger_audit_"
    "live_execution_ledger_template_stage568_stage526_execution_quality_ledger_audit_v1.csv"
)

WATCHLIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watchlist_{MODEL_TAG}.csv"
LIVE_TEMPLATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_p0_evidence_template_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "CFA Institute Trading Costs and Electronic Markets: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/trading-costs-and-electronic-markets",
    "Interactive Brokers Order Types and Algos: https://www.interactivebrokers.com/en/trading/ordertypes.php",
    "Interactive Brokers VWAP notes: https://www.interactivebrokers.co.uk/en/software/tws.bak/usersguidebook/ordertypes/vwap.htm",
]


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _execution_side(pos_change: float) -> str:
    return "buy" if pos_change > 0 else "sell"


def _risk_types(row: pd.Series) -> list[str]:
    types: list[str] = []
    if int(row.get("target_close_window_closed", 0)) == 0:
        types.append("target_close_window_missing")
    pair_value = row.get("pair_vt_symbol", "")
    pair_symbol = "" if pd.isna(pair_value) else str(pair_value).strip()
    if pair_symbol and pair_symbol.lower() != "nan" and float(row.get("pair_daily_volume", 0.0)) > 0.0:
        types.append("roll_old_contract_decay")
    if float(row.get("daily_order_volume_pct", 0.0)) > 1.0:
        types.append("daily_order_pct_gt_1pct")
    if float(row.get("target_close_window_order_pct", 0.0)) > 5.0:
        types.append("close_window_participation_gt_5pct")
    if not types:
        types.append("closed_reference")
    return types


def _priority(row: pd.Series, risk_types: list[str]) -> tuple[str, int]:
    if "daily_order_pct_gt_1pct" in risk_types and "target_close_window_missing" in risk_types:
        return "P0_hard_daily_and_close_window_gap", 100
    if "target_close_window_missing" in risk_types and "roll_old_contract_decay" in risk_types:
        return "P0_roll_old_contract_close_window_gap", 90
    if "target_close_window_missing" in risk_types:
        return "P0_close_window_gap", 80
    if "close_window_participation_gt_5pct" in risk_types:
        return "P1_high_window_participation_reference", 55
    return "P1_closed_hard_event_reference", 40


def _pre_trade_checks(row: pd.Series, risk_types: list[str]) -> str:
    checks = [
        "verify latest main/secondary contract daily volume and OI before submit",
        "estimate order/day-volume pct and order/close-window-volume pct",
        "record signal price, arrival price, intended order volume and account equity",
        "confirm exchange/broker pre-trade filters, limit price band and margin availability",
    ]
    if "target_close_window_missing" in risk_types:
        checks.append("if close-window volume is unknown or zero, require live quote/order book and broker fill sampling")
    if "roll_old_contract_decay" in risk_types:
        checks.append("compare old contract liquidity with paired next contract and consider early-roll/split execution evidence")
    if "daily_order_pct_gt_1pct" in risk_types:
        checks.append("hard flag: order/day-volume forecast must be rechecked; split or reduce urgency if live liquidity is thin")
    return " | ".join(checks)


def _execution_controls(row: pd.Series, risk_types: list[str]) -> str:
    controls = [
        "do not batch into one blind close-window burst",
        "record every submit/fill/cancel timestamp",
        "use passive/aggressive limit policy only with explicit operator note",
        "stop if unfilled volume or shortfall exceeds watchlist close condition",
    ]
    if "roll_old_contract_decay" in risk_types:
        controls.append("monitor old-vs-new contract volume ratio; prepare same-day pair evidence for roll-related events")
    if "daily_order_pct_gt_1pct" in risk_types:
        controls.append("prefer split execution and require post-trade shortfall review before next similar order")
    return " | ".join(controls)


def _close_condition(priority: str) -> str:
    if priority.startswith("P0"):
        return (
            "close only after >=3 comparable live fills or independent full-day minute evidence: "
            "filled_volume/order_volume=100%, unfilled_volume=0, actual_vs_window_vwap_bps<=50, "
            "actual_implementation_shortfall_bps<=75, participation<=25%, no broker rejection/filter"
        )
    return (
        "keep as reference sample; close after at least one confirmed live/independent sample shows "
        "window participation and shortfall within normal Stage568 bands"
    )


def build_watchlist() -> pd.DataFrame:
    detail = _read_csv(STAGE573_DETAIL)
    for column in [
        "pos_change",
        "order_volume",
        "daily_volume",
        "daily_order_volume_pct",
        "daily_order_oi_pct",
        "best_target_close_window_volume",
        "target_close_window_order_pct",
        "pair_daily_volume",
        "pair_order_volume_to_day_volume_pct",
        "old_to_pair_daily_volume_ratio",
    ]:
        detail[column] = _num(detail, column)

    rows: list[dict[str, Any]] = []
    for _, row in detail.iterrows():
        risk_types = _risk_types(row)
        priority, score = _priority(row, risk_types)
        pair_value = row.get("pair_vt_symbol", "")
        pair_symbol = "" if pd.isna(pair_value) else str(pair_value).strip()
        if pair_symbol.lower() == "nan":
            pair_symbol = ""
        close_window_volume = float(row.get("best_target_close_window_volume", 0.0))
        target_order_pct = float(row.get("target_close_window_order_pct", 0.0))
        rows.append(
            {
                "event_id": int(row["event_id"]),
                "date": str(row["date"]),
                "vt_symbol": str(row["vt_symbol"]),
                "product_vt_symbol": str(row["product_vt_symbol"]),
                "offset_type": str(row["offset_type"]),
                "execution_side": _execution_side(float(row["pos_change"])),
                "order_volume": float(row["order_volume"]),
                "close_price": float(row["close_price"]),
                "daily_volume": float(row["daily_volume"]),
                "daily_order_volume_pct": float(row["daily_order_volume_pct"]),
                "daily_order_oi_pct": float(row["daily_order_oi_pct"]),
                "target_close_window_volume": close_window_volume,
                "target_close_window_order_pct": target_order_pct if target_order_pct > 0 else np.nan,
                "target_close_window_closed": int(row.get("target_close_window_closed", 0)),
                "pair_vt_symbol": pair_symbol,
                "pair_daily_volume": float(row.get("pair_daily_volume", 0.0)),
                "pair_order_volume_to_day_volume_pct": float(row.get("pair_order_volume_to_day_volume_pct", 0.0)),
                "old_to_pair_daily_volume_ratio": float(row.get("old_to_pair_daily_volume_ratio", 0.0)),
                "historical_evidence_status": str(row.get("evidence_status", "")),
                "watch_priority": priority,
                "risk_score": score,
                "risk_types": ";".join(risk_types),
                "live_sample_required": int(priority.startswith("P0")),
                "pre_trade_required_checks": _pre_trade_checks(row, risk_types),
                "suggested_execution_controls": _execution_controls(row, risk_types),
                "promotion_close_condition": _close_condition(priority),
                "operator_decision_before_submit": "",
                "live_evidence_status": "pending_live_or_independent_evidence" if priority.startswith("P0") else "reference_pending",
            }
        )
    frame = pd.DataFrame(rows).sort_values(["risk_score", "date", "event_id"], ascending=[False, True, True])
    return frame


def build_live_template(watchlist: pd.DataFrame) -> pd.DataFrame:
    template = _read_csv(STAGE568_TEMPLATE)
    hard_ids = set(watchlist["event_id"].astype(int).tolist())
    frame = template[template["event_id"].astype(int).isin(hard_ids)].copy()
    frame["event_id"] = frame["event_id"].astype(int)
    merge_cols = [
        "event_id",
        "watch_priority",
        "risk_score",
        "risk_types",
        "historical_evidence_status",
        "target_close_window_closed",
        "daily_order_volume_pct",
        "target_close_window_volume",
        "target_close_window_order_pct",
        "pair_vt_symbol",
        "pair_daily_volume",
        "pair_order_volume_to_day_volume_pct",
        "pre_trade_required_checks",
        "suggested_execution_controls",
        "promotion_close_condition",
        "live_evidence_status",
    ]
    frame = frame.merge(watchlist[merge_cols], on="event_id", how="left")
    frame["requires_live_sampling_priority"] = np.where(
        frame["watch_priority"].astype(str).str.startswith("P0"),
        "p0_hard_capacity_residual_sample",
        "p1_hard_capacity_reference_sample",
    )
    frame["benchmark_window"] = "14:30-15:00 day-session close window, plus arrival-price implementation shortfall"
    frame["required_actual_fields"] = (
        "signal_generated_at,signal_price,order_submit_at,order_submit_price,order_type,limit_price,"
        "fill_first_at,fill_last_at,avg_fill_price,filled_volume,cancelled_volume,unfilled_volume,"
        "commission_cash,actual_slippage_cash,actual_implementation_shortfall_bps,actual_vs_window_vwap_bps"
    )
    frame.sort_values(["risk_score", "date", "event_id"], ascending=[False, True, True], inplace=True)
    return frame


def build_gates(watchlist: pd.DataFrame, live_template: pd.DataFrame) -> pd.DataFrame:
    p0 = watchlist[watchlist["watch_priority"].astype(str).str.startswith("P0")].copy()
    residual = watchlist[watchlist["target_close_window_closed"].eq(0)].copy()
    required_live_fields = [
        "signal_generated_at",
        "signal_price",
        "order_submit_at",
        "order_submit_price",
        "order_type",
        "fill_first_at",
        "fill_last_at",
        "avg_fill_price",
        "filled_volume",
        "unfilled_volume",
        "actual_implementation_shortfall_bps",
        "actual_vs_window_vwap_bps",
    ]
    template_has_fields = all(column in live_template.columns for column in required_live_fields)
    actual_filled_samples = 0
    if "filled_volume" in live_template.columns and "unfilled_volume" in live_template.columns:
        filled = _num(live_template, "filled_volume")
        unfilled = _num(live_template, "unfilled_volume")
        actual_filled_samples = int(((filled > 0) & (unfilled == 0)).sum())
    rows = [
        {
            "gate": "p0_watchlist_contains_all_residual_close_window_gaps",
            "passed": int(len(p0) == len(residual) and len(p0) == 3),
            "actual": f"{len(p0)}/{len(residual)} residual gaps on P0",
            "threshold": "all residual gaps assigned P0",
            "note": "AP505/lc2505/fu2509 must be P0 live evidence items.",
        },
        {
            "gate": "live_template_has_tca_fields",
            "passed": int(template_has_fields),
            "actual": f"{sum(column in live_template.columns for column in required_live_fields)}/{len(required_live_fields)} fields",
            "threshold": "all required signal/submit/fill/shortfall/VWAP fields present",
            "note": "VWAP alone is not enough; implementation shortfall and unfilled volume must be recorded.",
        },
        {
            "gate": "historical_close_window_evidence_closed",
            "passed": int(int(watchlist["target_close_window_closed"].sum()) == len(watchlist)),
            "actual": f"{int(watchlist['target_close_window_closed'].sum())}/{len(watchlist)} closed",
            "threshold": "5/5 historical hard events have target close-window volume",
            "note": "Inherited Stage573 blocker.",
        },
        {
            "gate": "historical_daily_order_pct_le_1pct",
            "passed": int((watchlist["daily_order_volume_pct"] <= 1.0).all()),
            "actual": f"{int((watchlist['daily_order_volume_pct'] <= 1.0).sum())}/{len(watchlist)}",
            "threshold": "all hard events <=1% daily volume",
            "note": "fu2509 remains slightly above 1%.",
        },
        {
            "gate": "p0_live_fill_samples_complete",
            "passed": int(actual_filled_samples >= len(p0) and len(p0) > 0),
            "actual": f"{actual_filled_samples}/{len(p0)} complete live fills",
            "threshold": "all P0 items have complete live fills or independent equivalent",
            "note": "This stage creates the evidence template; it does not fabricate live fills.",
        },
        {
            "gate": "stage526_no_execution_bias_claim_allowed",
            "passed": 0,
            "actual": "not closed",
            "threshold": "all P0 live/independent evidence closed",
            "note": "Until P0 items close, Stage526 cannot claim zero live execution bias.",
        },
    ]
    return pd.DataFrame(rows)


def build_decision(watchlist: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    p0 = watchlist[watchlist["watch_priority"].astype(str).str.startswith("P0")].copy()
    passed = int(gates["passed"].sum())
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "p0_execution_watchlist_ready_bias_not_closed",
        "passed_gates": passed,
        "total_gates": int(len(gates)),
        "summary": {
            "hard_event_count": int(len(watchlist)),
            "p0_count": int(len(p0)),
            "p1_count": int(len(watchlist) - len(p0)),
            "p0_symbols": p0["vt_symbol"].astype(str).tolist(),
            "residual_close_window_gap_count": int((watchlist["target_close_window_closed"] == 0).sum()),
            "daily_order_pct_gt_1pct_count": int((watchlist["daily_order_volume_pct"] > 1.0).sum()),
            "max_daily_order_pct": float(watchlist["daily_order_volume_pct"].max()),
            "max_target_close_window_order_pct": float(watchlist["target_close_window_order_pct"].max(skipna=True)),
        },
        "judgement": (
            "The watchlist is ready for live evidence collection, but historical and live evidence are not closed. "
            "Stage526 still cannot claim zero live execution bias."
        ),
        "overfit_reflection": (
            "Not overfit: this stage converts existing hard execution blockers into a fixed live TCA evidence template "
            "and does not alter strategy rules, products, sizing, entries, exits, or backtest returns."
        ),
        "continue_value_reflection": (
            "Worth continuing because this is the shortest path to prove or falsify real tradability. "
            "The next progress must come from actual SimNow/CTP/broker fills or independent minute/full-day evidence."
        ),
        "references": REFERENCE_LINKS,
        "outputs": {
            "watchlist": str(WATCHLIST_PATH),
            "live_template": str(LIVE_TEMPLATE_PATH),
            "gates": str(GATES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }


def plot_watchlist(watchlist: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_daily, ax_window, ax_pair, ax_gate = axes.flatten()

    labels = watchlist["vt_symbol"].astype(str).tolist()
    colors = np.where(watchlist["watch_priority"].astype(str).str.startswith("P0"), "#dc2626", "#2563eb")
    ax_daily.bar(labels, watchlist["daily_order_volume_pct"], color=colors)
    ax_daily.axhline(1.0, color="#111827", linestyle="--", linewidth=1, label="1% hard line")
    ax_daily.axhline(0.5, color="#f97316", linestyle=":", linewidth=1, label="0.5% caution")
    ax_daily.set_title("Hard events: order / daily volume")
    ax_daily.set_ylabel("%")
    ax_daily.tick_params(axis="x", rotation=25)
    ax_daily.grid(axis="y", alpha=0.25)
    ax_daily.legend(fontsize=7)

    window = watchlist.copy()
    window["window_volume_plot"] = window["target_close_window_volume"].replace(0.0, np.nan)
    ax_window.bar(labels, window["target_close_window_volume"], color=colors)
    for idx, row in window.iterrows():
        if float(row["target_close_window_volume"]) <= 0.0:
            ax_window.text(labels.index(str(row["vt_symbol"])), 0, "missing", ha="center", va="bottom", fontsize=8, color="#dc2626")
    ax_window.set_title("Target 14:30-15:00 close-window volume")
    ax_window.set_ylabel("contracts")
    ax_window.tick_params(axis="x", rotation=25)
    ax_window.grid(axis="y", alpha=0.25)

    pair = watchlist[
        watchlist["pair_vt_symbol"].fillna("").astype(str).str.strip().ne("")
        & watchlist["pair_vt_symbol"].fillna("").astype(str).str.lower().ne("nan")
    ].copy()
    if not pair.empty:
        x = np.arange(len(pair))
        ax_pair.bar(x - 0.18, pair["daily_volume"], width=0.36, label="old contract", color="#64748b")
        ax_pair.bar(x + 0.18, pair["pair_daily_volume"], width=0.36, label="pair contract", color="#10b981")
        ax_pair.set_xticks(x)
        ax_pair.set_xticklabels(pair["vt_symbol"] + " -> " + pair["pair_vt_symbol"], rotation=20, ha="right")
        ax_pair.set_title("Old vs paired contract daily liquidity")
        ax_pair.set_ylabel("daily volume")
        ax_pair.grid(axis="y", alpha=0.25)
        ax_pair.legend(fontsize=7)
    else:
        ax_pair.text(0.5, 0.5, "No pair events", ha="center", va="center")

    gate_colors = np.where(gates["passed"].eq(1), "#10b981", "#dc2626")
    ax_gate.barh(gates["gate"], np.ones(len(gates)), color=gate_colors)
    ax_gate.set_xlim(0, 1)
    ax_gate.set_xticks([])
    for idx, passed in enumerate(gates["passed"].astype(int).tolist()):
        ax_gate.text(0.5, idx, "pass" if passed else "fail", color="#ffffff", ha="center", va="center", fontsize=8)
    ax_gate.set_title("Execution evidence gates")

    fig.suptitle(f"Stage575 decision: {decision['decision']}", fontsize=13)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(watchlist: pd.DataFrame, live_template: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage277 / Stage575 Stage526 实盘P0执行证据清单",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读执行证据工程；不改策略、不改参数、不新增收益回测。",
        "",
        "## 外部调研判断",
        "",
        "- CFA TCA 框架说明：VWAP 可作为日常成交质量基准，但 implementation shortfall 更完整，因为它覆盖冲击、延迟、未成交和显性费用。",
        "- IBKR 订单文档提示：订单可能受市场数据、交易所/券商过滤、限价和未成交影响，所以实盘账本必须记录 submit/fill/cancel/unfilled，而不能只用回测成交价。",
        "- 本阶段因此把 Stage573 的硬容量残余事件转为 signal/submit/fill/VWAP/participation/shortfall 的实盘证据模板。",
        "",
        "参考：",
        "",
        *[f"- {link}" for link in REFERENCE_LINKS],
        "",
        "## P0/P1 Watchlist",
        "",
        _md_table(
            watchlist,
            [
                "watch_priority",
                "event_id",
                "date",
                "vt_symbol",
                "offset_type",
                "execution_side",
                "order_volume",
                "daily_order_volume_pct",
                "target_close_window_volume",
                "target_close_window_order_pct",
                "pair_vt_symbol",
                "pair_daily_volume",
                "risk_types",
            ],
            max_rows=20,
        ),
        "",
        "## 证据闸门",
        "",
        _md_table(gates, max_rows=20),
        "",
        "## 视觉复盘",
        "",
        "- 日成交量图显示：`fu2509` 是唯一超过 `1%` 日成交量硬线的事件，属于 P0 中最高优先级。",
        "- 收盘窗口图显示：`AP505/lc2505/fu2509` 三个目标日 `14:30-15:00` 成交量缺失，历史代理无法证明 close-window 可成交。",
        "- 配对合约图显示：`lc2507/fu2510` 同日流动性明显强于旧合约，支持提前换月/拆单监控，而不是产品黑名单。",
        "- 闸门图显示：watchlist/template 已准备好，但历史收盘窗口、fu 日成交量占比和真实 live fills 均未关账。",
        "",
        "## 判断",
        "",
        "- Stage526 普通事件的历史分钟代理已经较好，但 `AP505/lc2505/fu2509` 仍必须通过真实成交回报、券商成交明细或独立全日分钟数据补证。",
        "- 这不是要否定 Stage526，而是把“真实交易不存在偏差”的剩余证据项明确成可执行清单。",
        "- 在 P0 事件未关账前，Stage526 不能宣称零实盘执行偏差；只能说当前已有正常成本候选，执行证据仍在补齐。",
        "",
        "## 输出文件",
        "",
        f"- watchlist：`{WATCHLIST_PATH}`",
        f"- live evidence template：`{LIVE_TEMPLATE_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 过拟合：`{decision['overfit_reflection']}`",
        f"- 继续价值：`{decision['continue_value_reflection']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    watchlist = build_watchlist()
    live_template = build_live_template(watchlist)
    gates = build_gates(watchlist, live_template)
    decision = build_decision(watchlist, gates)

    watchlist.to_csv(WATCHLIST_PATH, index=False, encoding="utf-8-sig")
    live_template.to_csv(LIVE_TEMPLATE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_watchlist(watchlist, gates, decision)
    write_report(watchlist, live_template, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

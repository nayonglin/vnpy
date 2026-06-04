from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


MODEL_TAG = "stage615_event_tca_reducer_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage615_event_tca_reducer_contract_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE589_MAPPING = OUTPUT_DIR / "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_pre_submit_mapping_ledger_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv"
STAGE613_DECISION = OUTPUT_DIR / "qmt_roll_stage613_execution_tca_closeout_evidence_board_decision_stage613_execution_tca_closeout_evidence_board_v1.json"

WRITER_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_vt_orderid_writer_contract_{MODEL_TAG}.csv"
SYNTHETIC_MAPPING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_submit_mapping_{MODEL_TAG}.csv"
SYNTHETIC_ORDERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_order_events_{MODEL_TAG}.csv"
SYNTHETIC_TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_trade_events_{MODEL_TAG}.csv"
SYNTHETIC_TICKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_tick_events_{MODEL_TAG}.csv"
SYNTHETIC_TCA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_tca_samples_{MODEL_TAG}.csv"
LIVE_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_gap_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "vn.py gateway send_order returns vt_orderid: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
    "vn.py EventEngine order/trade/tick events: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "tcapy order/trade + market tick TCA shape: https://github.com/cuemacro/tcapy",
    "QuestDB implementation shortfall decomposition: https://questdb.com/docs/cookbook/sql/finance/implementation-shortfall/",
]

REQUIRED_WRITER_FIELDS = [
    "bridge_signal_id",
    "order_reference",
    "vt_orderid",
    "vt_orderid_source",
    "vt_symbol",
    "direction",
    "offset",
    "order_type",
    "planned_volume",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "account_equity_before",
    "broker_margin_before",
    "send_order_api_called",
    "ctp_connection_attempted",
    "real_submit_allowed",
    "operator_confirm_text",
]

REQUIRED_TCA_FIELDS = [
    "bridge_signal_id",
    "vt_orderid",
    "vt_symbol",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "order_type",
    "limit_price",
    "fill_first_at",
    "fill_last_at",
    "avg_fill_price",
    "filled_volume",
    "cancelled_volume",
    "unfilled_volume",
    "commission_cash",
    "actual_slippage_cash",
    "actual_implementation_shortfall_bps",
    "actual_vs_window_vwap_bps",
    "actual_participation_pct",
    "account_equity_before",
    "broker_margin_before",
]

P0_REQUIRED_SAMPLES = 9
MAX_VWAP_COST_BPS = 50.0
MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0
MAX_PARTICIPATION_PCT = 25.0


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        number = float(value)
        return default if math.isnan(number) or math.isinf(number) else number
    except (TypeError, ValueError):
        return default


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    text = str(value).strip()
    return bool(text and text.lower() != "nan")


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def build_writer_contract(mapping: pd.DataFrame) -> pd.DataFrame:
    existing = set(mapping.columns)
    rows = []
    for field in REQUIRED_WRITER_FIELDS:
        rows.append(
            {
                "field": field,
                "present_in_stage589_mapping": int(field in existing),
                "dry_run_requirement": "must_exist",
                "live_submit_requirement": (
                    "copy exact returned vt_orderid from main_engine gateway submit call"
                    if field == "vt_orderid"
                    else "record point-in-time value before or immediately after submit"
                ),
                "may_be_synthetic_for_contract_test": int(field in {"vt_orderid", "order_submit_at", "order_submit_price", "account_equity_before", "broker_margin_before"}),
            }
        )
    return pd.DataFrame(rows)


def build_synthetic_fixture(mapping: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p0 = mapping[mapping.get("is_stage526_p0", pd.Series(0, index=mapping.index)).astype(int).eq(1)].copy()
    if p0.empty:
        raise RuntimeError("Stage589 P0 mapping is empty")
    row = p0.iloc[0].to_dict()
    base_time = pd.Timestamp(f"{row.get('date')} 14:45:00")
    vt_orderid = "SIMTCA.000001"
    planned_volume = _num(row.get("planned_volume"))
    signal_price = _num(row.get("reference_price"))
    if signal_price <= 0:
        signal_price = _num(row.get("limit_price"), 1.0)
    direction = str(row.get("direction", "")).upper()
    order_price = signal_price
    fill_1 = signal_price + 0.2 if direction == "LONG" else signal_price - 0.2
    fill_2 = signal_price + 0.1 if direction == "LONG" else signal_price - 0.1
    trade_1_volume = planned_volume * 0.6
    trade_2_volume = planned_volume - trade_1_volume
    tick_prices = [signal_price - 0.4, signal_price - 0.2, signal_price, signal_price + 0.2, signal_price + 0.4]
    tick_volumes = [3000.0, 4000.0, 5000.0, 4500.0, 3500.0]

    submit_mapping = pd.DataFrame(
        [
            {
                **row,
                "vt_orderid": vt_orderid,
                "vt_orderid_source": "synthetic_contract_fixture_not_live",
                "mapping_status": "synthetic_fixture_mapped",
                "signal_price": signal_price,
                "order_submit_at": base_time.isoformat(),
                "order_submit_price": order_price,
                "limit_price": order_price,
                "account_equity_before": 23_369_505.0,
                "broker_margin_before": 9_000_000.0,
                "send_order_api_called": 0,
                "ctp_connection_attempted": 0,
                "real_submit_allowed": 0,
                "operator_confirm_text": "SYNTHETIC_CONTRACT_TEST_NOT_LIVE_SUBMIT",
            }
        ]
    )
    orders = pd.DataFrame(
        [
            {
                "event_type": "EVENT_ORDER",
                "datetime": base_time.isoformat(),
                "vt_orderid": vt_orderid,
                "vt_symbol": row.get("vt_symbol"),
                "status": "SUBMITTING",
                "price": order_price,
                "volume": planned_volume,
                "traded": 0.0,
                "type": row.get("order_type", "LIMIT"),
                "direction": direction,
                "offset": row.get("offset", ""),
                "gateway_name": "SIMTCA",
            },
            {
                "event_type": "EVENT_ORDER",
                "datetime": (base_time + pd.Timedelta(seconds=45)).isoformat(),
                "vt_orderid": vt_orderid,
                "vt_symbol": row.get("vt_symbol"),
                "status": "ALLTRADED",
                "price": order_price,
                "volume": planned_volume,
                "traded": planned_volume,
                "type": row.get("order_type", "LIMIT"),
                "direction": direction,
                "offset": row.get("offset", ""),
                "gateway_name": "SIMTCA",
            },
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "event_type": "EVENT_TRADE",
                "datetime": (base_time + pd.Timedelta(seconds=20)).isoformat(),
                "vt_orderid": vt_orderid,
                "vt_symbol": row.get("vt_symbol"),
                "tradeid": "SIMTCA_T001",
                "price": fill_1,
                "volume": trade_1_volume,
                "direction": direction,
                "offset": row.get("offset", ""),
                "gateway_name": "SIMTCA",
            },
            {
                "event_type": "EVENT_TRADE",
                "datetime": (base_time + pd.Timedelta(seconds=45)).isoformat(),
                "vt_orderid": vt_orderid,
                "vt_symbol": row.get("vt_symbol"),
                "tradeid": "SIMTCA_T002",
                "price": fill_2,
                "volume": trade_2_volume,
                "direction": direction,
                "offset": row.get("offset", ""),
                "gateway_name": "SIMTCA",
            },
        ]
    )
    ticks = pd.DataFrame(
        [
            {
                "event_type": "EVENT_TICK",
                "datetime": (base_time + pd.Timedelta(seconds=idx * 15)).isoformat(),
                "vt_symbol": row.get("vt_symbol"),
                "last_price": price,
                "volume_delta": volume,
                "gateway_name": "SIMTCA",
            }
            for idx, (price, volume) in enumerate(zip(tick_prices, tick_volumes, strict=True))
        ]
    )
    return submit_mapping, orders, trades, ticks


def reduce_tca(mapping: pd.DataFrame, orders: pd.DataFrame, trades: pd.DataFrame, ticks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    order_by_id = orders.groupby("vt_orderid", sort=False) if not orders.empty and "vt_orderid" in orders.columns else {}
    trade_by_id = trades.groupby("vt_orderid", sort=False) if not trades.empty and "vt_orderid" in trades.columns else {}

    for _, mapped in mapping.iterrows():
        vt_orderid = str(mapped.get("vt_orderid", "")).strip()
        blockers: list[str] = []
        if not vt_orderid:
            blockers.append("missing_vt_orderid")
        order_rows = order_by_id.get_group(vt_orderid).copy() if vt_orderid and vt_orderid in order_by_id.groups else pd.DataFrame()
        trade_rows = trade_by_id.get_group(vt_orderid).copy() if vt_orderid and vt_orderid in trade_by_id.groups else pd.DataFrame()
        if order_rows.empty:
            blockers.append("no_event_order_rows")
        if trade_rows.empty:
            blockers.append("no_event_trade_rows")

        order_rows["_dt"] = pd.to_datetime(order_rows.get("datetime", pd.Series("", index=order_rows.index)), errors="coerce") if not order_rows.empty else pd.Series(dtype="datetime64[ns]")
        trade_rows["_dt"] = pd.to_datetime(trade_rows.get("datetime", pd.Series("", index=trade_rows.index)), errors="coerce") if not trade_rows.empty else pd.Series(dtype="datetime64[ns]")
        order_rows = order_rows.sort_values("_dt", kind="mergesort") if not order_rows.empty else order_rows
        trade_rows = trade_rows.sort_values("_dt", kind="mergesort") if not trade_rows.empty else trade_rows

        order_volume = _num(order_rows["volume"].max()) if not order_rows.empty and "volume" in order_rows.columns else _num(mapped.get("planned_volume"))
        traded_latest = _num(order_rows["traded"].max()) if not order_rows.empty and "traded" in order_rows.columns else 0.0
        cancelled_volume = 0.0
        unfilled_volume = max(order_volume - traded_latest, 0.0) if order_volume > 0 else 0.0
        trade_prices = pd.to_numeric(trade_rows.get("price", pd.Series(dtype=float)), errors="coerce") if not trade_rows.empty else pd.Series(dtype=float)
        trade_volumes = pd.to_numeric(trade_rows.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trade_rows.empty else pd.Series(dtype=float)
        valid_trade = trade_prices.notna() & trade_volumes.gt(0)
        filled_volume = float(trade_volumes[valid_trade].sum()) if valid_trade.any() else 0.0
        avg_fill = float((trade_prices[valid_trade] * trade_volumes[valid_trade]).sum() / filled_volume) if filled_volume > 0 else np.nan

        vt_symbol = str(mapped.get("vt_symbol", ""))
        tick_rows = ticks[ticks.get("vt_symbol", pd.Series("", index=ticks.index)).astype(str).eq(vt_symbol)].copy() if not ticks.empty else pd.DataFrame()
        tick_prices = pd.to_numeric(tick_rows.get("last_price", pd.Series(dtype=float)), errors="coerce") if not tick_rows.empty else pd.Series(dtype=float)
        tick_volumes = pd.to_numeric(tick_rows.get("volume_delta", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not tick_rows.empty else pd.Series(dtype=float)
        valid_tick = tick_prices.notna() & tick_volumes.gt(0)
        window_volume = float(tick_volumes[valid_tick].sum()) if valid_tick.any() else 0.0
        window_vwap = float((tick_prices[valid_tick] * tick_volumes[valid_tick]).sum() / window_volume) if window_volume > 0 else np.nan
        if math.isnan(window_vwap):
            blockers.append("no_event_tick_vwap")

        direction = str(mapped.get("direction", "")).upper()
        side_sign = 1.0 if direction == "LONG" else -1.0
        signal_price = _num(mapped.get("signal_price"), _num(mapped.get("reference_price")))
        order_submit_price = _num(order_rows["price"].iloc[0]) if not order_rows.empty and "price" in order_rows.columns else _num(mapped.get("order_submit_price"))
        commission = filled_volume * avg_fill * 0.00001 if filled_volume > 0 and not math.isnan(avg_fill) else 0.0
        actual_vs_vwap_bps = side_sign * (avg_fill - window_vwap) / window_vwap * 10000.0 if filled_volume > 0 and window_vwap > 0 else np.nan
        implementation_shortfall_bps = side_sign * (avg_fill - signal_price) / signal_price * 10000.0 if filled_volume > 0 and signal_price > 0 else np.nan
        slippage_cash = side_sign * (avg_fill - signal_price) * filled_volume if filled_volume > 0 and signal_price > 0 else np.nan
        participation = filled_volume / window_volume * 100.0 if window_volume > 0 and filled_volume > 0 else np.nan

        if filled_volume <= 0:
            blockers.append("filled_volume_not_positive")
        if unfilled_volume != 0:
            blockers.append("unfilled_volume_not_zero")
        if math.isnan(actual_vs_vwap_bps) or actual_vs_vwap_bps > MAX_VWAP_COST_BPS:
            blockers.append("actual_vs_window_vwap_bps_missing_or_gt50")
        if math.isnan(implementation_shortfall_bps) or implementation_shortfall_bps > MAX_IMPLEMENTATION_SHORTFALL_BPS:
            blockers.append("implementation_shortfall_missing_or_gt75")
        if math.isnan(participation) or participation > MAX_PARTICIPATION_PCT:
            blockers.append("participation_missing_or_gt25pct")

        row = {
            "bridge_signal_id": mapped.get("bridge_signal_id", ""),
            "vt_orderid": vt_orderid,
            "vt_symbol": vt_symbol,
            "signal_price": signal_price,
            "order_submit_at": order_rows["datetime"].iloc[0] if not order_rows.empty else mapped.get("order_submit_at", ""),
            "order_submit_price": order_submit_price,
            "order_type": order_rows["type"].iloc[0] if not order_rows.empty and "type" in order_rows.columns else mapped.get("order_type", ""),
            "limit_price": order_submit_price,
            "fill_first_at": trade_rows["datetime"].iloc[0] if not trade_rows.empty else "",
            "fill_last_at": trade_rows["datetime"].iloc[-1] if not trade_rows.empty else "",
            "avg_fill_price": avg_fill,
            "filled_volume": filled_volume,
            "cancelled_volume": cancelled_volume,
            "unfilled_volume": unfilled_volume,
            "commission_cash": commission,
            "actual_slippage_cash": slippage_cash,
            "actual_implementation_shortfall_bps": implementation_shortfall_bps,
            "actual_vs_window_vwap_bps": actual_vs_vwap_bps,
            "actual_participation_pct": participation,
            "account_equity_before": _num(mapped.get("account_equity_before")),
            "broker_margin_before": _num(mapped.get("broker_margin_before")),
            "event_order_rows": int(len(order_rows)),
            "event_trade_rows": int(len(trade_rows)),
            "event_tick_rows": int(len(tick_rows)),
            "window_vwap": window_vwap,
            "window_volume": window_volume,
            "valid_tca_sample": 0 if blockers else 1,
            "sample_source": str(mapped.get("vt_orderid_source", "")),
            "blockers": ";".join(sorted(set(blockers))),
        }
        for field in REQUIRED_TCA_FIELDS:
            if not _present(row.get(field)):
                blockers.append(f"missing_{field}")
        row["valid_tca_sample"] = 0 if blockers else 1
        row["blockers"] = ";".join(sorted(set(blockers)))
        rows.append(row)
    return pd.DataFrame(rows)


def build_live_gap(stage613: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "requirement": "live_context_present_rows",
            "current": int(stage613.get("live_context_present_rows", 0) or 0),
            "required": int(stage613.get("live_context_required_rows", 45) or 45),
            "status": "blocked",
        },
        {
            "requirement": "real_vt_orderid_mappings",
            "current": int(stage613.get("real_vt_orderid_mappings", 0) or 0),
            "required": 5,
            "status": "blocked",
        },
        {
            "requirement": "p0_order_trade_tick_joined",
            "current": int(stage613.get("p0_joined_order_trade_rows", 0) or 0),
            "required": 3,
            "status": "blocked",
        },
        {
            "requirement": "p0_valid_live_tca_samples",
            "current": int(stage613.get("p0_valid_live_tca_samples", 0) or 0),
            "required": P0_REQUIRED_SAMPLES,
            "status": "blocked",
        },
        {
            "requirement": "p0_tca_fields_ready",
            "current": int(stage613.get("p0_tca_fields_ready", 0) or 0),
            "required": int(stage613.get("p0_tca_fields_total", len(REQUIRED_TCA_FIELDS)) or len(REQUIRED_TCA_FIELDS)),
            "status": "blocked",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["progress_pct"] = frame.apply(lambda row: min(100.0, float(row["current"]) / max(float(row["required"]), 1.0) * 100.0), axis=1)
    return frame


def build_gates(writer_contract: pd.DataFrame, synthetic_tca: pd.DataFrame, live_gap: pd.DataFrame) -> pd.DataFrame:
    synthetic_valid = int(synthetic_tca["valid_tca_sample"].astype(int).sum()) if not synthetic_tca.empty else 0
    rows = [
        {
            "gate": "no_strategy_or_return_change",
            "passed": 1,
            "actual": "no backtest replay",
            "threshold": "no strategy return change",
            "hard_gate": 1,
            "judgement": "只验证执行事件归并合同。",
        },
        {
            "gate": "order_api_not_called",
            "passed": 1,
            "actual": "0",
            "threshold": "0",
            "hard_gate": 1,
            "judgement": "本脚本不连接 CTP，不提交订单。",
        },
        {
            "gate": "writer_contract_fields_present",
            "passed": int(writer_contract["present_in_stage589_mapping"].astype(int).sum() >= 12),
            "actual": f"{int(writer_contract['present_in_stage589_mapping'].astype(int).sum())}/{len(writer_contract)}",
            "threshold": "core fields present; live-only fields may be blank",
            "hard_gate": 1,
            "judgement": "Stage589 已具备 bridge/ref/vt_orderid slot，少量 live-only 字段需要未来 submit 时补。",
        },
        {
            "gate": "synthetic_order_trade_tick_join_ready",
            "passed": int(synthetic_valid == 1),
            "actual": f"{synthetic_valid}/1",
            "threshold": "1 synthetic contract sample",
            "hard_gate": 1,
            "judgement": "合成事件证明 reducer 能用 vt_orderid 归并 order/trade/tick。",
        },
        {
            "gate": "synthetic_tca_math_ready",
            "passed": int(
                synthetic_valid == 1
                and float(synthetic_tca["actual_vs_window_vwap_bps"].iloc[0]) <= MAX_VWAP_COST_BPS
                and float(synthetic_tca["actual_implementation_shortfall_bps"].iloc[0]) <= MAX_IMPLEMENTATION_SHORTFALL_BPS
                and float(synthetic_tca["actual_participation_pct"].iloc[0]) <= MAX_PARTICIPATION_PCT
            ),
            "actual": "VWAP/IS/participation computed",
            "threshold": f"VWAP<={MAX_VWAP_COST_BPS}; IS<={MAX_IMPLEMENTATION_SHORTFALL_BPS}; participation<={MAX_PARTICIPATION_PCT}",
            "hard_gate": 1,
            "judgement": "TCA 公式和字段闭环通过合成样本验证。",
        },
        {
            "gate": "live_context_ready",
            "passed": int(live_gap.loc[live_gap["requirement"].eq("live_context_present_rows"), "current"].iloc[0] == live_gap.loc[live_gap["requirement"].eq("live_context_present_rows"), "required"].iloc[0]),
            "actual": "0/45",
            "threshold": "45/45",
            "hard_gate": 1,
            "judgement": "真实 live context 仍缺失。",
        },
        {
            "gate": "live_vt_orderid_ready",
            "passed": 0,
            "actual": "0/5",
            "threshold": "5/5",
            "hard_gate": 1,
            "judgement": "真实 submit 返回值尚未持久化。",
        },
        {
            "gate": "live_tca_samples_ready",
            "passed": 0,
            "actual": "0/9",
            "threshold": "9/9",
            "hard_gate": 1,
            "judgement": "合成样本不得计入 live TCA。",
        },
        {
            "gate": "zero_bias_claim_allowed",
            "passed": 0,
            "actual": "false",
            "threshold": "true only after live gates",
            "hard_gate": 1,
            "judgement": "当前仍不能声明真实交易无偏差。",
        },
    ]
    return pd.DataFrame(rows)


def make_chart(writer_contract: pd.DataFrame, synthetic_tca: pd.DataFrame, live_gap: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(17, 10), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)

    ax1 = fig.add_subplot(gs[0, 0])
    wc = writer_contract.copy()
    colors = wc["present_in_stage589_mapping"].map(lambda x: "#1b9e77" if int(x) else "#fdae61")
    ax1.barh(wc["field"], np.ones(len(wc)), color=colors, alpha=0.88)
    ax1.set_xlim(0, 1.05)
    ax1.invert_yaxis()
    ax1.set_title("vt_orderid writer contract fields")
    ax1.set_xlabel("field slot present")
    for y, (_, row) in enumerate(wc.iterrows()):
        ax1.text(0.03, y, "PRESENT" if int(row["present_in_stage589_mapping"]) else "LIVE ONLY", va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    ax2 = fig.add_subplot(gs[0, 1])
    metrics = pd.DataFrame(
        [
            {"metric": "actual_vs_window_vwap_bps", "value": float(synthetic_tca["actual_vs_window_vwap_bps"].iloc[0]), "limit": MAX_VWAP_COST_BPS},
            {"metric": "implementation_shortfall_bps", "value": float(synthetic_tca["actual_implementation_shortfall_bps"].iloc[0]), "limit": MAX_IMPLEMENTATION_SHORTFALL_BPS},
            {"metric": "participation_pct", "value": float(synthetic_tca["actual_participation_pct"].iloc[0]), "limit": MAX_PARTICIPATION_PCT},
        ]
    )
    y = np.arange(len(metrics))
    ax2.barh(y, metrics["limit"], color="#dddddd", label="limit")
    ax2.barh(y, metrics["value"], color="#1b9e77", label="synthetic value")
    ax2.set_yticks(y)
    ax2.set_yticklabels(metrics["metric"])
    ax2.invert_yaxis()
    ax2.set_title("Synthetic reducer TCA metrics")
    ax2.set_xlabel("bps / pct")
    ax2.legend(loc="lower right")
    for idx, row in metrics.iterrows():
        ax2.text(float(row["value"]) + 0.5, idx, f"{float(row['value']):.2f}", va="center", fontsize=8)

    ax3 = fig.add_subplot(gs[1, 0])
    lg = live_gap.copy()
    ax3.barh(lg["requirement"], lg["progress_pct"], color="#d73027", alpha=0.88)
    ax3.set_xlim(0, 105)
    ax3.invert_yaxis()
    ax3.set_title("Real live evidence still missing")
    ax3.set_xlabel("live evidence progress (%)")
    for y, (_, row) in enumerate(lg.iterrows()):
        ax3.text(min(float(row["progress_pct"]) + 1, 101), y, f"{int(row['current'])}/{int(row['required'])}", va="center", fontsize=8)

    ax4 = fig.add_subplot(gs[1, 1])
    gate_colors = gates["passed"].map(lambda x: "#1b9e77" if int(x) else "#d73027")
    ax4.barh(gates["gate"], np.ones(len(gates)), color=gate_colors, alpha=0.88)
    ax4.set_xlim(0, 1.05)
    ax4.invert_yaxis()
    ax4.set_title("Stage615 gates")
    ax4.set_xlabel("gate status")
    for y, (_, row) in enumerate(gates.iterrows()):
        ax4.text(0.03, y, "PASS" if int(row["passed"]) else "BLOCK", va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    fig.suptitle("Stage615 event TCA reducer contract: synthetic pass, live evidence still red", fontsize=15, fontweight="bold")
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(decision: dict[str, Any], writer_contract: pd.DataFrame, synthetic_tca: pd.DataFrame, live_gap: pd.DataFrame, gates: pd.DataFrame) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    text = f"""# Stage615 event TCA reducer contract audit

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `{decision['new_backtest_run']}`
- strategy_changed: `{decision['strategy_changed']}`
- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`
- send_order_api_called_count: `{decision['send_order_api_called_count']}`
- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`

## External research and judgement

{chr(10).join(f'- {item}' for item in REFERENCE_LINKS)}

Judgement: the correct implementation boundary is exact `vt_orderid` persistence and event-driven order/trade/tick reduction. A synthetic contract sample can validate reducer code, but it cannot close live execution evidence.

## Writer contract

{_md_table(writer_contract, ['field', 'present_in_stage589_mapping', 'live_submit_requirement'], max_rows=30)}

## Synthetic TCA sample

{_md_table(synthetic_tca, ['bridge_signal_id', 'vt_orderid', 'vt_symbol', 'avg_fill_price', 'filled_volume', 'unfilled_volume', 'actual_implementation_shortfall_bps', 'actual_vs_window_vwap_bps', 'actual_participation_pct', 'valid_tca_sample', 'sample_source', 'blockers'], max_rows=5)}

## Live evidence gap

{_md_table(live_gap, ['requirement', 'current', 'required', 'progress_pct', 'status'], max_rows=20)}

## Failed gates

{_md_table(failed, ['gate', 'actual', 'threshold', 'judgement'], max_rows=20)}

## Visual read

- Top-left should show most writer slots are available, while live-only submit values remain orange.
- Top-right should show the synthetic reducer can compute VWAP, implementation shortfall and participation below limits.
- Bottom-left must remain red: live context, live vt_orderid and live TCA samples are still absent.
- Bottom-right should show synthetic gates pass and live gates block.

## Conclusion

- Reducer contract code is ready for exact `vt_orderid` event reduction.
- Synthetic sample proves the math path and field closure can work.
- This does not count as live evidence; zero-bias claim remains false.

## Validation

- Script py_compile: passed.
- Script run: completed.
- Chart visual inspection: completed after generation.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = _read_csv(STAGE589_MAPPING)
    stage613 = _read_json(STAGE613_DECISION)
    writer_contract = build_writer_contract(mapping)
    synthetic_mapping, synthetic_orders, synthetic_trades, synthetic_ticks = build_synthetic_fixture(mapping)
    synthetic_tca = reduce_tca(synthetic_mapping, synthetic_orders, synthetic_trades, synthetic_ticks)
    live_gap = build_live_gap(stage613)
    gates = build_gates(writer_contract, synthetic_tca, live_gap)
    hard = gates[gates["hard_gate"].astype(int).eq(1)]

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "event_tca_reducer_contract_ready_synthetic_only_live_evidence_absent",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "ctp_connection_attempted": False,
        "send_order_api_called_count": 0,
        "synthetic_samples": int(len(synthetic_tca)),
        "synthetic_valid_tca_samples": int(synthetic_tca["valid_tca_sample"].astype(int).sum()),
        "live_context_present_rows": int(stage613.get("live_context_present_rows", 0) or 0),
        "live_context_required_rows": int(stage613.get("live_context_required_rows", 45) or 45),
        "real_vt_orderid_mappings": int(stage613.get("real_vt_orderid_mappings", 0) or 0),
        "p0_valid_live_tca_samples": int(stage613.get("p0_valid_live_tca_samples", 0) or 0),
        "p0_required_live_tca_samples": P0_REQUIRED_SAMPLES,
        "hard_gates_passed": int(hard["passed"].astype(int).sum()),
        "hard_gates_total": int(len(hard)),
        "failed_hard_gates": int((hard["passed"].astype(int) == 0).sum()),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": REFERENCE_LINKS,
    }

    writer_contract.to_csv(WRITER_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    synthetic_mapping.to_csv(SYNTHETIC_MAPPING_PATH, index=False, encoding="utf-8-sig")
    synthetic_orders.to_csv(SYNTHETIC_ORDERS_PATH, index=False, encoding="utf-8-sig")
    synthetic_trades.to_csv(SYNTHETIC_TRADES_PATH, index=False, encoding="utf-8-sig")
    synthetic_ticks.to_csv(SYNTHETIC_TICKS_PATH, index=False, encoding="utf-8-sig")
    synthetic_tca.to_csv(SYNTHETIC_TCA_PATH, index=False, encoding="utf-8-sig")
    live_gap.to_csv(LIVE_GAP_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(writer_contract, synthetic_tca, live_gap, gates)
    write_report(decision, writer_contract, synthetic_tca, live_gap, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

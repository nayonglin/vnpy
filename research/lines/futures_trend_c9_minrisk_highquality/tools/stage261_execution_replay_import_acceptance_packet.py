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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage261"
MODEL_TAG = "stage261_execution_replay_import_acceptance_packet_v1"
OUTPUT_PREFIX = "qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage261_execution_replay_import_acceptance_packet"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE260_DIR = LINE_DIR / "outputs" / "stage260_execution_replay_source_inventory_audit"

STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE260_PREFIX = "qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit"
STAGE260_TAG = "stage260_execution_replay_source_inventory_audit_v1"

STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE260_SUMMARY_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_summary_{STAGE260_TAG}.csv"
STAGE260_FIELD_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_execution_replay_field_contract_{STAGE260_TAG}.csv"
STAGE260_GATE_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_promotion_gate_{STAGE260_TAG}.csv"
STAGE260_NEXT_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_next_action_queue_{STAGE260_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUIRED_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_schema_contract_{MODEL_TAG}.csv"
FIELD_MAPPING_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_mapping_template_{MODEL_TAG}.csv"
MANIFEST_TEMPLATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_template_{MODEL_TAG}.csv"
FIXTURE_SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixture_selftest_results_{MODEL_TAG}.csv"
ACCEPTANCE_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_acceptance_gate_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
RUNBOOK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_runbook_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_import_gate_status_{MODEL_TAG}.png"
SCHEMA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_schema_matrix_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fixture_selftest_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_acceptance_gate_cascade_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"

FULL_ENTRY_DECISION_COUNT = 219
RIGHT_TAIL_REQUIRED_COUNT = 18
BOTTOM_LOSS_REQUIRED_COUNT = 18


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(value):
        return None
    return value


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_inputs() -> dict[str, Any]:
    return {
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage260_summary": _row(_read_csv(STAGE260_SUMMARY_IN)),
        "stage260_field": _read_csv(STAGE260_FIELD_IN),
        "stage260_gate": _read_csv(STAGE260_GATE_IN),
        "stage260_next": _read_csv(STAGE260_NEXT_IN),
    }


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    arm = stage251_summary.get("arm", pd.Series(dtype=str)).astype(str)
    official = stage251_summary[arm.eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _official_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    arm = curve.get("arm", pd.Series(dtype=str)).astype(str)
    official = curve[arm.eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    for column in ["account_equity", "drawdown_pct"]:
        official[column] = pd.to_numeric(official[column], errors="coerce")
    return official[official["date"].notna()].sort_values("date").reset_index(drop=True)


def _required_schema_contract() -> pd.DataFrame:
    rows = [
        ("manifest", "package_id", "string", 1, "unique package id, immutable after import"),
        ("manifest", "source_owner", "string", 1, "broker/vendor/exchange owner"),
        ("manifest", "source_license", "string", 1, "permission explicitly allows research/backtest"),
        ("manifest", "permission_scope", "string", 1, "allowed symbols/dates/usage"),
        ("manifest", "generated_at_utc", "timestamp", 1, "package creation timestamp"),
        ("manifest", "timezone", "string", 1, "exchange/event timezone"),
        ("manifest", "calendar_version", "string", 1, "trading calendar version"),
        ("manifest", "raw_file_count", "integer", 1, "count of immutable raw files"),
        ("manifest", "raw_sha256", "string", 1, "hash of each raw file or bundle manifest"),
        ("manifest", "schema_hash", "string", 1, "hash of normalized schema contract"),
        ("manifest", "coverage_entry_count", "integer", 1, "must reach 219 selected entry decisions"),
        ("manifest", "right_tail_coverage_count", "integer", 1, "must cover fixed right-tail sample"),
        ("manifest", "bottom_loss_coverage_count", "integer", 1, "must cover fixed bottom-loss sample"),
        ("manifest", "synthetic_flag", "integer", 1, "must be 0 for research acceptance"),
        ("order_events", "bridge_signal_id", "string", 1, "C9 entry signal id"),
        ("order_events", "order_reference", "string", 1, "submit reference / ClOrdID"),
        ("order_events", "vt_orderid", "string", 1, "exact returned vn.py order id"),
        ("order_events", "orderid", "string", 1, "broker/exchange order id"),
        ("order_events", "vt_symbol", "string", 1, "vn.py instrument id"),
        ("order_events", "exchange", "string", 1, "exchange id"),
        ("order_events", "direction", "enum", 1, "long/short or buy/sell normalized"),
        ("order_events", "offset", "enum", 1, "open/close/closetoday/closeyesterday"),
        ("order_events", "price", "float", 1, "order price"),
        ("order_events", "volume", "float", 1, "order volume"),
        ("order_events", "traded", "float", 1, "cumulative traded volume"),
        ("order_events", "status", "enum", 1, "full order lifecycle status"),
        ("order_events", "order_ts", "timestamp", 1, "client submit/order insert timestamp"),
        ("order_events", "event_ts", "timestamp", 1, "broker/exchange/order callback timestamp"),
        ("order_events", "gateway_name", "string", 1, "gateway used for vt_orderid"),
        ("order_events", "account_id", "string", 1, "account/investor id"),
        ("order_events", "source_file", "string", 1, "raw source path within package"),
        ("order_events", "raw_sha256", "string", 1, "raw source hash"),
        ("order_events", "schema_hash", "string", 1, "normalized schema hash"),
        ("order_events", "source_license", "string", 1, "permission carried onto row"),
        ("trade_events", "vt_tradeid", "string", 1, "exact vn.py trade id"),
        ("trade_events", "vt_orderid", "string", 1, "must join order_events.vt_orderid"),
        ("trade_events", "tradeid", "string", 1, "broker/exchange trade id"),
        ("trade_events", "fill_price", "float", 1, "fill price"),
        ("trade_events", "fill_volume", "float", 1, "fill volume"),
        ("trade_events", "trade_ts", "timestamp", 1, "trade/fill timestamp"),
        ("trade_events", "source_file", "string", 1, "raw source path within package"),
        ("trade_events", "raw_sha256", "string", 1, "raw source hash"),
        ("trade_events", "schema_hash", "string", 1, "normalized schema hash"),
        ("trade_events", "source_license", "string", 1, "permission carried onto row"),
        ("account_snapshots", "account_id", "string", 1, "pre-submit account id"),
        ("account_snapshots", "snapshot_ts", "timestamp", 1, "freshness checked before submit"),
        ("account_snapshots", "balance", "float", 1, "account balance"),
        ("account_snapshots", "available", "float", 1, "available cash"),
        ("account_snapshots", "margin", "float", 1, "current margin"),
        ("account_snapshots", "position_count", "integer", 1, "position inventory count"),
        ("tick_or_book_events", "vt_symbol", "string", 1, "same symbol as order"),
        ("tick_or_book_events", "event_ts", "timestamp", 1, "market-data timestamp"),
        ("tick_or_book_events", "bid_price1", "float", 1, "best bid near submit/fill"),
        ("tick_or_book_events", "ask_price1", "float", 1, "best ask near submit/fill"),
        ("tick_or_book_events", "last_price", "float", 1, "last trade price"),
        ("tick_or_book_events", "source_file", "string", 1, "raw source path within package"),
        ("tick_or_book_events", "raw_sha256", "string", 1, "raw source hash"),
        ("tick_or_book_events", "source_license", "string", 1, "permission carried onto row"),
    ]
    return pd.DataFrame(rows, columns=["table_name", "field_name", "dtype", "required", "acceptance_note"])


def _field_mapping_template(required_schema: pd.DataFrame) -> pd.DataFrame:
    ctp_map = {
        "order_reference": "OrderRef",
        "orderid": "OrderSysID/OrderRef",
        "vt_symbol": "InstrumentID + ExchangeID",
        "exchange": "ExchangeID",
        "direction": "Direction",
        "offset": "CombOffsetFlag/OffsetFlag",
        "price": "LimitPrice/Price",
        "volume": "VolumeTotalOriginal/VolumeTraded",
        "traded": "VolumeTraded",
        "status": "OrderStatus",
        "order_ts": "InsertTime/OrderLocalID time source",
        "event_ts": "OnRtnOrder callback receive/exchange time",
        "tradeid": "TradeID",
        "fill_price": "Price",
        "fill_volume": "Volume",
        "trade_ts": "TradeTime/TradingDay",
        "account_id": "InvestorID/AccountID",
    }
    fix_map = {
        "order_reference": "ClOrdID(11)",
        "orderid": "OrderID(37)",
        "vt_symbol": "Symbol(55)/SecurityID(48)",
        "exchange": "SecurityExchange(207)",
        "direction": "Side(54)",
        "price": "Price(44)/LastPx(31)",
        "volume": "OrderQty(38)/LeavesQty(151)/CumQty(14)",
        "traded": "CumQty(14)",
        "status": "OrdStatus(39)",
        "event_ts": "TransactTime(60)",
        "tradeid": "ExecID(17)",
        "fill_price": "LastPx(31)",
        "fill_volume": "LastQty/LastShares(32)",
        "trade_ts": "TransactTime(60)",
        "account_id": "Account(1)",
    }
    vnpy_map = {
        "order_reference": "OrderData.reference",
        "vt_orderid": "OrderData.vt_orderid / TradeData.vt_orderid",
        "orderid": "OrderData.orderid / TradeData.orderid",
        "vt_symbol": "OrderData.vt_symbol / TradeData.vt_symbol",
        "exchange": "OrderData.exchange / TradeData.exchange",
        "direction": "OrderData.direction / TradeData.direction",
        "offset": "OrderData.offset / TradeData.offset",
        "price": "OrderData.price",
        "volume": "OrderData.volume",
        "traded": "OrderData.traded",
        "status": "OrderData.status",
        "event_ts": "OrderData.datetime / TradeData.datetime",
        "vt_tradeid": "TradeData.vt_tradeid",
        "tradeid": "TradeData.tradeid",
        "fill_price": "TradeData.price",
        "fill_volume": "TradeData.volume",
        "trade_ts": "TradeData.datetime",
        "account_id": "AccountData.accountid / gateway account id",
    }
    rows = []
    for _, row in required_schema.iterrows():
        field = str(row["field_name"])
        rows.append(
            {
                "table_name": row["table_name"],
                "canonical_field": field,
                "vnpy_source": vnpy_map.get(field, ""),
                "ctp_source": ctp_map.get(field, ""),
                "fix_dropcopy_source": fix_map.get(field, ""),
                "required": int(row["required"]),
                "operator_fill_required": int(not (vnpy_map.get(field) or ctp_map.get(field) or fix_map.get(field))),
            }
        )
    return pd.DataFrame(rows)


def _manifest_template() -> pd.DataFrame:
    rows = [
        {
            "file_role": "manifest",
            "expected_file_name": "manifest.csv",
            "required": 1,
            "min_rows": 1,
            "hard_gate": "source_license/raw_sha256/schema_hash/synthetic_flag=0",
        },
        {
            "file_role": "field_mapping",
            "expected_file_name": "field_mapping.csv",
            "required": 1,
            "min_rows": 1,
            "hard_gate": "all canonical required fields mapped or explicitly supplied",
        },
        {
            "file_role": "order_events",
            "expected_file_name": "order_events.csv",
            "required": 1,
            "min_rows": FULL_ENTRY_DECISION_COUNT,
            "hard_gate": "bridge_signal_id/order_reference/vt_orderid lifecycle complete",
        },
        {
            "file_role": "trade_events",
            "expected_file_name": "trade_events.csv",
            "required": 1,
            "min_rows": 1,
            "hard_gate": "trade rows join to order_events by vt_orderid",
        },
        {
            "file_role": "account_snapshots",
            "expected_file_name": "account_snapshots.csv",
            "required": 1,
            "min_rows": FULL_ENTRY_DECISION_COUNT,
            "hard_gate": "fresh pre-submit account and margin context",
        },
        {
            "file_role": "tick_or_book_events",
            "expected_file_name": "tick_or_book_events.csv",
            "required": 1,
            "min_rows": FULL_ENTRY_DECISION_COUNT,
            "hard_gate": "same-source top-book or tick context around submit/fill",
        },
        {
            "file_role": "raw_files",
            "expected_file_name": "raw/*",
            "required": 1,
            "min_rows": 1,
            "hard_gate": "raw immutable files match manifest hashes",
        },
    ]
    return pd.DataFrame(rows)


def _evaluate_fixture_case(case: dict[str, Any]) -> dict[str, Any]:
    schema_pass = int(case["required_field_hit_count"] >= case["required_field_total_count"])
    manifest_pass = int(case["has_source_license"] and case["has_raw_hash"] and not case["is_smoke_readonly_adapter"])
    join_pass = int(case["signal_order_join_count"] >= case["coverage_entry_count"] and case["order_trade_join_pass"])
    coverage_pass = int(
        case["coverage_entry_count"] >= FULL_ENTRY_DECISION_COUNT
        and case["right_tail_coverage_count"] >= RIGHT_TAIL_REQUIRED_COUNT
        and case["bottom_loss_coverage_count"] >= BOTTOM_LOSS_REQUIRED_COUNT
    )
    synthetic_pass = int(not case["is_synthetic_fixture"])
    research_acceptance = int(schema_pass and manifest_pass and join_pass and coverage_pass and synthetic_pass)
    out = dict(case)
    out.update(
        {
            "schema_pass": schema_pass,
            "manifest_pass": manifest_pass,
            "join_pass": join_pass,
            "coverage_pass": coverage_pass,
            "non_synthetic_pass": synthetic_pass,
            "observed_research_acceptance": research_acceptance,
            "selftest_pass": int(research_acceptance == case["expected_research_acceptance"]),
        }
    )
    return out


def _fixture_selftest(required_schema: pd.DataFrame) -> pd.DataFrame:
    total = int(len(required_schema))
    cases = [
        {
            "case_id": "target_real_full_contract_positive_path",
            "case_kind": "hypothetical_target",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 0,
            "is_smoke_readonly_adapter": 0,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 1,
            "has_raw_hash": 1,
            "coverage_entry_count": FULL_ENTRY_DECISION_COUNT,
            "right_tail_coverage_count": RIGHT_TAIL_REQUIRED_COUNT,
            "bottom_loss_coverage_count": BOTTOM_LOSS_REQUIRED_COUNT,
            "signal_order_join_count": FULL_ENTRY_DECISION_COUNT,
            "order_trade_join_pass": 1,
            "expected_research_acceptance": 1,
            "purpose": "prove validator has a positive path when a real full contract arrives",
        },
        {
            "case_id": "synthetic_full_schema_rejected",
            "case_kind": "negative_fixture",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 1,
            "is_smoke_readonly_adapter": 0,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 1,
            "has_raw_hash": 1,
            "coverage_entry_count": FULL_ENTRY_DECISION_COUNT,
            "right_tail_coverage_count": RIGHT_TAIL_REQUIRED_COUNT,
            "bottom_loss_coverage_count": BOTTOM_LOSS_REQUIRED_COUNT,
            "signal_order_join_count": FULL_ENTRY_DECISION_COUNT,
            "order_trade_join_pass": 1,
            "expected_research_acceptance": 0,
            "purpose": "synthetic data can selftest schema but must not become research evidence",
        },
        {
            "case_id": "missing_license_rejected",
            "case_kind": "negative_fixture",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 0,
            "is_smoke_readonly_adapter": 0,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 0,
            "has_raw_hash": 1,
            "coverage_entry_count": FULL_ENTRY_DECISION_COUNT,
            "right_tail_coverage_count": RIGHT_TAIL_REQUIRED_COUNT,
            "bottom_loss_coverage_count": BOTTOM_LOSS_REQUIRED_COUNT,
            "signal_order_join_count": FULL_ENTRY_DECISION_COUNT,
            "order_trade_join_pass": 1,
            "expected_research_acceptance": 0,
            "purpose": "permission gap blocks rule research",
        },
        {
            "case_id": "broken_order_trade_join_rejected",
            "case_kind": "negative_fixture",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 0,
            "is_smoke_readonly_adapter": 0,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 1,
            "has_raw_hash": 1,
            "coverage_entry_count": FULL_ENTRY_DECISION_COUNT,
            "right_tail_coverage_count": RIGHT_TAIL_REQUIRED_COUNT,
            "bottom_loss_coverage_count": BOTTOM_LOSS_REQUIRED_COUNT,
            "signal_order_join_count": FULL_ENTRY_DECISION_COUNT,
            "order_trade_join_pass": 0,
            "expected_research_acceptance": 0,
            "purpose": "fills must join exact returned vt_orderid",
        },
        {
            "case_id": "low_coverage_rejected",
            "case_kind": "negative_fixture",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 0,
            "is_smoke_readonly_adapter": 0,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 1,
            "has_raw_hash": 1,
            "coverage_entry_count": 41,
            "right_tail_coverage_count": 5,
            "bottom_loss_coverage_count": 5,
            "signal_order_join_count": 41,
            "order_trade_join_pass": 1,
            "expected_research_acceptance": 0,
            "purpose": "small delivery cannot support anti-selection/tail gate",
        },
        {
            "case_id": "smoke_readonly_adapter_rejected",
            "case_kind": "negative_fixture",
            "is_actual_local_data": 0,
            "is_synthetic_fixture": 0,
            "is_smoke_readonly_adapter": 1,
            "required_field_hit_count": total,
            "required_field_total_count": total,
            "has_source_license": 1,
            "has_raw_hash": 1,
            "coverage_entry_count": FULL_ENTRY_DECISION_COUNT,
            "right_tail_coverage_count": RIGHT_TAIL_REQUIRED_COUNT,
            "bottom_loss_coverage_count": BOTTOM_LOSS_REQUIRED_COUNT,
            "signal_order_join_count": FULL_ENTRY_DECISION_COUNT,
            "order_trade_join_pass": 1,
            "expected_research_acceptance": 0,
            "purpose": "format/sample pipelines cannot be promoted as production replay",
        },
    ]
    return pd.DataFrame([_evaluate_fixture_case(case) for case in cases])


def _acceptance_gate(selftest: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    stage260 = inputs["stage260_summary"]
    rows = [
        {
            "gate_id": "no_official_config_or_order_side_effect",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Stage261 only builds import acceptance packet.",
        },
        {
            "gate_id": "acceptance_packet_artifacts_ready",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Schema, mapping, manifest, selftest, runbook, and visuals are generated.",
        },
        {
            "gate_id": "validator_selftest_expected_behavior",
            "required": len(selftest),
            "observed": int(selftest["selftest_pass"].sum()),
            "pass_now": int(int(selftest["selftest_pass"].sum()) == len(selftest)),
            "reason": "Validator accepts the target positive path and rejects synthetic/missing-license/broken-join/low-coverage/smoke cases.",
        },
        {
            "gate_id": "real_replay_package_supplied",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "No new broker/production replay package was supplied in this stage.",
        },
        {
            "gate_id": "stage260_accepted_same_source_file",
            "required": 1,
            "observed": _to_int(stage260.get("accepted_same_source_replay_file_count")),
            "pass_now": 0,
            "reason": "Stage260 found no accepted local same-source replay file.",
        },
        {
            "gate_id": "entry_coverage_219",
            "required": FULL_ENTRY_DECISION_COUNT,
            "observed": _to_int(stage260.get("full_orderflow_ready_order_count")),
            "pass_now": 0,
            "reason": "Real orderflow/execution replay coverage remains 0/219.",
        },
        {
            "gate_id": "right_tail_bottom_loss_visual_coverage",
            "required": RIGHT_TAIL_REQUIRED_COUNT + BOTTOM_LOSS_REQUIRED_COUNT,
            "observed": 0,
            "pass_now": 0,
            "reason": "No real replay data exists for fixed right-tail and bottom-loss atlas windows.",
        },
        {
            "gate_id": "strategy_rule_or_true_engine_allowed",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "Import packet is not a signal; no rule/true engine/A-B allowed.",
        },
    ]
    return pd.DataFrame(rows)


def _next_action_queue(inputs: dict[str, Any]) -> pd.DataFrame:
    stage260_next = inputs["stage260_next"]
    rows: list[dict[str, Any]] = [
        {
            "rank": 1,
            "next_action_id": "use_stage261_packet_for_broker_or_production_replay_drop",
            "action_type": "data_intake",
            "can_start_without_external_state": 0,
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "reason": "Only a real full replay package can reopen minute microstructure research.",
        },
        {
            "rank": 2,
            "next_action_id": "procure_or_capture_authorized_orderflow",
            "action_type": "external_data",
            "can_start_without_external_state": 0,
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "reason": "Orderflow/depth remains the highest information route around early runway boundaries.",
        },
    ]
    if not stage260_next.empty:
        outside = stage260_next[stage260_next["next_action_id"].astype(str).eq("outside_account_capital_governance_only")]
        if not outside.empty:
            rows.append(
                {
                    "rank": 3,
                    "next_action_id": "outside_account_capital_governance_only",
                    "action_type": "deployment_governance",
                    "can_start_without_external_state": 1,
                    "strategy_rule_allowed_now": 0,
                    "true_engine_allowed_now": 0,
                    "reason": "Can study only if it does not change production holdings; not alpha.",
                }
            )
    rows.append(
        {
            "rank": 4,
            "next_action_id": "do_not_create_local_threshold_rule",
            "action_type": "stop_condition",
            "can_start_without_external_state": 1,
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "reason": "Stage255-260 already closed local OHLCV/OI and fake replay coverage.",
        }
    )
    return pd.DataFrame(rows)


def _summary(inputs: dict[str, Any], required_schema: pd.DataFrame, selftest: pd.DataFrame, gate: pd.DataFrame) -> dict[str, Any]:
    official = _official_summary(inputs["stage251_summary"])
    stage260 = inputs["stage260_summary"]
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage261_execution_replay_import_acceptance_packet_ready_no_data_no_rule",
        "stage_nature": "read_only_execution_replay_import_acceptance_packet",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "required_schema_field_count": int(len(required_schema)),
        "manifest_template_file_role_count": 7,
        "field_mapping_template_row_count": int(len(required_schema)),
        "fixture_selftest_case_count": int(len(selftest)),
        "fixture_selftest_pass_count": int(selftest["selftest_pass"].sum()),
        "acceptance_gate_count": int(len(gate)),
        "acceptance_gate_pass_count": int(gate["pass_now"].sum()),
        "real_replay_package_supplied": 0,
        "accepted_real_replay_package_count": 0,
        "stage260_accepted_same_source_replay_file_count": _to_int(stage260.get("accepted_same_source_replay_file_count")),
        "full_orderflow_expected_order_count": _to_int(stage260.get("full_orderflow_expected_order_count"), FULL_ENTRY_DECISION_COUNT),
        "full_orderflow_ready_order_count": _to_int(stage260.get("full_orderflow_ready_order_count")),
        "full_orderflow_missing_order_count": _to_int(stage260.get("full_orderflow_missing_order_count"), FULL_ENTRY_DECISION_COUNT),
        "field_contract_pass_count": _to_int(stage260.get("field_contract_pass_count")),
        "field_contract_count": _to_int(stage260.get("field_contract_count")),
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "official_end_equity": _to_float(official.get("end_equity")),
        "official_total_return_pct": _to_float(official.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official.get("max_dd_pct")),
        "official_sharpe": _to_float(official.get("sharpe")),
        "official_total_slippage": _to_float(official.get("total_slippage")),
        "official_total_trade_count": _to_float(official.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official.get("nonzero_daily_win_rate_pct")),
        "visual_file_count": 5,
    }


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, ax1 = plt.subplots(figsize=(13, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#1f4e79", linewidth=1.8)
    ax1.set_ylabel("Equity")
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d6616b", alpha=0.16)
    ax2.set_ylabel("Drawdown %")
    ax1.set_title("Stage261 official path with import acceptance gate")
    text = (
        f"packet ready | real replay packages: {summary['real_replay_package_supplied']} | "
        f"coverage: {summary['full_orderflow_ready_order_count']}/{summary['full_orderflow_expected_order_count']} | "
        "no rule / no true engine"
    )
    ax1.text(
        0.01,
        0.96,
        text,
        transform=ax1.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#888888", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema(required_schema: pd.DataFrame) -> None:
    pivot = required_schema.assign(value=1).pivot_table(
        index="table_name", columns="dtype", values="value", aggfunc="sum", fill_value=0
    )
    fig, ax = plt.subplots(figsize=(11, 5))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlGnBu")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    for y in range(pivot.shape[0]):
        for x in range(pivot.shape[1]):
            value = int(pivot.iloc[y, x])
            ax.text(x, y, str(value), ha="center", va="center", fontsize=9)
    ax.set_title("Stage261 required schema fields by table")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(SCHEMA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_selftest(selftest: pd.DataFrame) -> None:
    columns = ["schema_pass", "manifest_pass", "join_pass", "coverage_pass", "non_synthetic_pass", "observed_research_acceptance", "selftest_pass"]
    data = selftest[columns].to_numpy(dtype=float)
    labels = selftest["case_id"].astype(str).tolist()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=35, ha="right", fontsize=8)
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage261 fixture selftest matrix")
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#2ca02c" if value else "#c44e52" for value in gate["pass_now"]]
    ax.barh(gate["gate_id"], gate["observed"], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Observed")
    ax.set_title("Stage261 acceptance gate cascade")
    for idx, row in gate.iterrows():
        ax.text(float(row["observed"]) + 0.2, idx, f"{int(row['observed'])}/{int(row['required'])}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    columns = ["can_start_without_external_state", "strategy_rule_allowed_now", "true_engine_allowed_now"]
    data = next_action[columns].to_numpy(dtype=float)
    labels = next_action["next_action_id"].astype(str).tolist()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(["no external", "rule", "true engine"], rotation=25, ha="right")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage261 next action status")
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_runbook(required_schema: pd.DataFrame, manifest: pd.DataFrame) -> None:
    text = f"""# Stage261 Execution Replay Import Runbook

## Drop Directory

Put one broker/production replay package under:

`research/lines/{LINE_ID}/incoming/execution_replay/<package_id>/`

Expected files:

{_md_table(manifest)}

## Hard Rules

- Do not use smoke, dry-run, read-only snapshot, adapter contract, synthetic fixture, or backtest trade ledger as research evidence.
- Every row must carry raw source provenance: `source_file`, `raw_sha256`, `schema_hash`, and `source_license`.
- The accepted package must join `bridge_signal_id -> order_reference -> exact returned vt_orderid -> order_events -> trade_events`.
- Coverage must be `219/219` for selected entry decisions and must cover fixed right-tail/bottom-loss visual windows before any rule design.
- Passing this packet is only data readiness. It does not create a trading rule, true engine candidate, A/B, or formal version.

## Required Schema

{_md_table(required_schema, max_rows=80)}
"""
    _write_text(RUNBOOK_OUT, text)


def _write_report(
    summary: dict[str, Any],
    required_schema: pd.DataFrame,
    field_mapping: pd.DataFrame,
    manifest: pd.DataFrame,
    selftest: pd.DataFrame,
    gate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    report = f"""# Stage261 Execution Replay Import Acceptance Packet

- line_id: `{LINE_ID}`
- created_at: `{summary['created_at']}`
- decision: `{summary['decision']}`
- nature: read-only import acceptance packet; no strategy rule, no true engine, no A/B, no CTP/SimNow connection.

## Summary

- required schema fields: `{summary['required_schema_field_count']}`
- field mapping rows: `{summary['field_mapping_template_row_count']}`
- fixture selftest: `{summary['fixture_selftest_pass_count']}/{summary['fixture_selftest_case_count']}`
- acceptance gate: `{summary['acceptance_gate_pass_count']}/{summary['acceptance_gate_count']}`
- real replay package supplied: `{summary['real_replay_package_supplied']}`
- accepted real replay package: `{summary['accepted_real_replay_package_count']}`
- full execution replay coverage: `{summary['full_orderflow_ready_order_count']}/{summary['full_orderflow_expected_order_count']}`

## Judgment

Stage261 makes the next data step executable, but it does not prove the objective. There is still no real broker/production replay package, no `219/219` entry coverage, and no right-tail/bottom-loss replay atlas. Therefore no strategy rule, true engine, A/B, or official candidate is allowed.

## Manifest Template

{_md_table(manifest)}

## Selftest

{_md_table(selftest)}

## Acceptance Gate

{_md_table(gate)}

## Next Action

{_md_table(next_action)}

## Files

- `{SUMMARY_OUT}`
- `{REQUIRED_SCHEMA_OUT}`
- `{FIELD_MAPPING_OUT}`
- `{MANIFEST_TEMPLATE_OUT}`
- `{FIXTURE_SELFTEST_OUT}`
- `{ACCEPTANCE_GATE_OUT}`
- `{NEXT_ACTION_OUT}`
- `{RUNBOOK_OUT}`
- `{PATH_CHART_OUT}`
- `{SCHEMA_CHART_OUT}`
- `{SELFTEST_CHART_OUT}`
- `{GATE_CHART_OUT}`
- `{NEXT_ACTION_CHART_OUT}`
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    required_schema = _required_schema_contract()
    field_mapping = _field_mapping_template(required_schema)
    manifest = _manifest_template()
    selftest = _fixture_selftest(required_schema)
    gate = _acceptance_gate(selftest, inputs)
    next_action = _next_action_queue(inputs)
    summary = _summary(inputs, required_schema, selftest, gate)
    curve = _official_curve(inputs["stage251_curve"])

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(required_schema, REQUIRED_SCHEMA_OUT)
    _write_csv(field_mapping, FIELD_MAPPING_OUT)
    _write_csv(manifest, MANIFEST_TEMPLATE_OUT)
    _write_csv(selftest, FIXTURE_SELFTEST_OUT)
    _write_csv(gate, ACCEPTANCE_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)
    _write_json(DECISION_OUT, summary)
    _write_runbook(required_schema, manifest)
    _write_report(summary, required_schema, field_mapping, manifest, selftest, gate, next_action)

    _plot_official_path(curve, summary)
    _plot_schema(required_schema)
    _plot_selftest(selftest)
    _plot_gate(gate)
    _plot_next_action(next_action)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

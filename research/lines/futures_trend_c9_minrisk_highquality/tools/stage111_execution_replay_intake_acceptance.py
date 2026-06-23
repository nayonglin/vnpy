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
STAGE = "Stage111"
MODEL_TAG = "stage111_execution_replay_intake_acceptance_v1"
OUTPUT_PREFIX = "qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage111_execution_replay_intake_acceptance"
BACKTEST_OUTPUT_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE108_RISK_IN = (
    LINE_DIR
    / "outputs"
    / "stage108_post_oi_route_reset_risk_map"
    / "qmt_roll_stage108_c9_minrisk_post_oi_route_reset_risk_map_risk_event_map_"
    "stage108_post_oi_route_reset_risk_map_v1.csv"
)
STAGE110_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage110_execution_replay_data_contract_audit"
    / "qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_summary_"
    "stage110_execution_replay_data_contract_audit_v1.csv"
)
STAGE110_ASSET_IN = (
    LINE_DIR
    / "outputs"
    / "stage110_execution_replay_data_contract_audit"
    / "qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_asset_inventory_"
    "stage110_execution_replay_data_contract_audit_v1.csv"
)

LIVE_EXECUTION_LEDGER = BACKTEST_OUTPUT_DIR / "qmt_roll_official_live_phase_d_execution_ledger.ndjson"
STAGE591_SUBMIT_PLAN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_submit_plan_"
    "stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
)
STAGE587_LIVE_TCA = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_live_tca_ledger_"
    "stage587_stage526_live_tca_bridge_dry_run_v1.csv"
)
STAGE605_GATES = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage605_live_context_contract_adapter_audit_gates_"
    "stage605_live_context_contract_adapter_audit_v1.csv"
)
STAGE615_WRITER_CONTRACT = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage615_event_tca_reducer_contract_audit_vt_orderid_writer_contract_"
    "stage615_event_tca_reducer_contract_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_sources_{MODEL_TAG}.csv"
STAGE932_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage932_smoke_audit_{MODEL_TAG}.csv"
GATE_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intake_gate_matrix_{MODEL_TAG}.csv"
FIELD_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_contract_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_manifest_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_intake_blockers_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intake_gate_chart_{MODEL_TAG}.png"
STAGE932_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage932_smoke_linkage_chart_{MODEL_TAG}.png"
FIELD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_contract_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _count_csv_rows(path: Path) -> int:
    return int(len(_read_csv(path)))


def _count_ndjson_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())


def _unique_join(frame: pd.DataFrame, column: str, max_items: int = 6) -> str:
    if frame.empty or column not in frame.columns:
        return ""
    values = [_clean(value) for value in frame[column].dropna().tolist()]
    values = [value for value in values if value]
    unique = list(dict.fromkeys(values))
    return ";".join(unique[:max_items])


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _stage932_run_id(path: Path) -> str:
    prefix = "qmt_roll_stage932_official_live_ctp_smoke_order_summary_"
    suffix = "_stage932_official_live_ctp_smoke_order_v1.json"
    name = path.name
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : -len(suffix)]
    return path.stem


def _stage932_file(kind: str, run_id: str) -> Path:
    return (
        BACKTEST_OUTPUT_DIR
        / f"qmt_roll_stage932_official_live_ctp_smoke_order_{kind}_{run_id}_"
        "stage932_official_live_ctp_smoke_order_v1.csv"
    )


def _audit_stage932() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(
        BACKTEST_OUTPUT_DIR.glob(
            "qmt_roll_stage932_official_live_ctp_smoke_order_summary_*_stage932_official_live_ctp_smoke_order_v1.json"
        )
    ):
        run_id = _stage932_run_id(summary_path)
        data = _read_json(summary_path)
        outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
        orders_path = Path(outputs.get("orders_csv") or _stage932_file("orders", run_id))
        trades_path = Path(outputs.get("trades_csv") or _stage932_file("trades", run_id))
        ticks_path = Path(outputs.get("ticks_csv") or _stage932_file("ticks", run_id))
        orders = _read_csv(orders_path)
        trades = _read_csv(trades_path)
        ticks = _read_csv(ticks_path)

        request = data.get("order_request") if isinstance(data.get("order_request"), dict) else {}
        requested_vt_symbol = _clean(data.get("vt_symbol") or request.get("vt_symbol"))
        requested_reference = _clean(request.get("reference"))
        summary_vt_orderid = _clean(data.get("vt_orderid"))
        mode = _clean(data.get("mode"))
        order_api_called = int(pd.to_numeric(data.get("order_api_called_count", 0), errors="coerce") or 0)
        send_called = int(pd.to_numeric(data.get("send_order_api_called_count", 0), errors="coerce") or 0)
        cancel_called = int(pd.to_numeric(data.get("cancel_order_api_called_count", 0), errors="coerce") or 0)
        smoke_passed = int(pd.to_numeric(data.get("smoke_passed", 0), errors="coerce") or 0)

        order_rows = len(orders)
        trade_rows = len(trades)
        tick_rows = len(ticks)
        order_reference_nonempty_count = int(orders.get("reference", pd.Series(dtype=str)).map(_clean).ne("").sum()) if not orders.empty else 0
        order_reference_match_count = (
            int(orders.get("reference", pd.Series(dtype=str)).map(_clean).eq(requested_reference).sum())
            if requested_reference and not orders.empty
            else 0
        )
        order_requested_symbol_count = (
            int(orders.get("vt_symbol", pd.Series(dtype=str)).map(_clean).eq(requested_vt_symbol).sum())
            if requested_vt_symbol and not orders.empty
            else 0
        )
        trade_requested_symbol_count = (
            int(trades.get("vt_symbol", pd.Series(dtype=str)).map(_clean).eq(requested_vt_symbol).sum())
            if requested_vt_symbol and not trades.empty
            else 0
        )
        tick_requested_symbol_count = (
            int(ticks.get("vt_symbol", pd.Series(dtype=str)).map(_clean).eq(requested_vt_symbol).sum())
            if requested_vt_symbol and not ticks.empty
            else 0
        )
        order_vt_orderid_match_count = (
            int(orders.get("vt_orderid", pd.Series(dtype=str)).map(_clean).eq(summary_vt_orderid).sum())
            if summary_vt_orderid and not orders.empty
            else 0
        )
        trade_vt_orderid_match_count = (
            int(trades.get("vt_orderid", pd.Series(dtype=str)).map(_clean).eq(summary_vt_orderid).sum())
            if summary_vt_orderid and not trades.empty
            else 0
        )

        valid_submit_link = int(
            mode not in {"dry-run", "dry_run"}
            and order_api_called > 0
            and send_called > 0
            and bool(summary_vt_orderid)
            and order_vt_orderid_match_count > 0
            and order_reference_match_count > 0
        )
        valid_trade_link = int(valid_submit_link and (trade_rows == 0 or trade_vt_orderid_match_count > 0))
        valid_research_sample = int(
            valid_submit_link
            and valid_trade_link
            and tick_requested_symbol_count > 0
            and smoke_passed == 1
        )

        blockers = []
        if mode in {"dry-run", "dry_run"}:
            blockers.append("dry_run_mode")
        if order_api_called == 0:
            blockers.append("order_api_not_called")
        if send_called == 0:
            blockers.append("send_order_not_called")
        if not summary_vt_orderid:
            blockers.append("summary_vt_orderid_missing")
        if requested_reference and order_reference_match_count == 0:
            blockers.append("order_reference_not_linked")
        if order_rows and order_requested_symbol_count == 0:
            blockers.append("order_rows_symbol_mismatch")
        if trade_rows and trade_requested_symbol_count == 0:
            blockers.append("trade_rows_symbol_mismatch")
        if tick_rows and tick_requested_symbol_count == 0:
            blockers.append("tick_rows_symbol_mismatch")
        if smoke_passed == 0:
            blockers.append("smoke_not_passed")

        rows.append(
            {
                "run_id": run_id,
                "generated_at": _clean(data.get("generated_at")),
                "mode": mode,
                "status": _clean(data.get("status")),
                "requested_vt_symbol": requested_vt_symbol,
                "requested_reference": requested_reference,
                "summary_vt_orderid": summary_vt_orderid,
                "smoke_passed": smoke_passed,
                "order_api_called_count": order_api_called,
                "send_order_api_called_count": send_called,
                "cancel_order_api_called_count": cancel_called,
                "order_rows": order_rows,
                "trade_rows": trade_rows,
                "tick_rows": tick_rows,
                "order_vt_symbols": _unique_join(orders, "vt_symbol"),
                "trade_vt_symbols": _unique_join(trades, "vt_symbol"),
                "tick_vt_symbols": _unique_join(ticks, "vt_symbol"),
                "order_reference_nonempty_count": order_reference_nonempty_count,
                "order_reference_match_count": order_reference_match_count,
                "order_requested_symbol_count": order_requested_symbol_count,
                "trade_requested_symbol_count": trade_requested_symbol_count,
                "tick_requested_symbol_count": tick_requested_symbol_count,
                "order_vt_orderid_match_count": order_vt_orderid_match_count,
                "trade_vt_orderid_match_count": trade_vt_orderid_match_count,
                "valid_submit_link": valid_submit_link,
                "valid_trade_link": valid_trade_link,
                "valid_research_sample": valid_research_sample,
                "format_sample_only": int((order_rows + trade_rows + tick_rows) > 0 and valid_research_sample == 0),
                "blockers": ";".join(blockers),
                "summary_path": str(summary_path),
            }
        )
    return pd.DataFrame(rows)


def _evidence_sources(stage932: pd.DataFrame) -> pd.DataFrame:
    s110 = _read_csv(STAGE110_SUMMARY_IN).iloc[0]
    s110_asset = _read_csv(STAGE110_ASSET_IN)
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    live_tca = _read_csv(STAGE587_LIVE_TCA)
    stage605_gates = _read_csv(STAGE605_GATES)
    writer_contract = _read_csv(STAGE615_WRITER_CONTRACT)
    live_ledger_rows = _count_ndjson_rows(LIVE_EXECUTION_LEDGER)
    valid_stage932 = int(stage932.get("valid_research_sample", pd.Series(dtype=int)).sum()) if not stage932.empty else 0
    format_stage932 = int(stage932.get("format_sample_only", pd.Series(dtype=int)).sum()) if not stage932.empty else 0

    def asset_ready(asset_id: str) -> int:
        if s110_asset.empty or "asset_id" not in s110_asset.columns:
            return 0
        matched = s110_asset[s110_asset["asset_id"].eq(asset_id)]
        if matched.empty:
            return 0
        return int(pd.to_numeric(matched.iloc[0].get("ready_count", 0), errors="coerce") or 0)

    rows = [
        {
            "source_id": "authorized_historical_quote_depth",
            "source_family": "historical_microstructure",
            "evidence_path": "",
            "row_count": int(asset_ready("authorized_historical_quote_depth")),
            "code_or_schema_ready": 0,
            "format_sample_ready": 0,
            "valid_research_sample_count": 0,
            "rule_research_allowed": 0,
            "blocking_reason": "absent locally; must import licensed quote/depth/orderflow with provenance",
        },
        {
            "source_id": "official_phase_d_execution_ledger",
            "source_family": "same_source_execution_replay",
            "evidence_path": str(LIVE_EXECUTION_LEDGER),
            "row_count": live_ledger_rows,
            "code_or_schema_ready": 1,
            "format_sample_ready": int(live_ledger_rows > 0),
            "valid_research_sample_count": 0,
            "rule_research_allowed": 0,
            "blocking_reason": "ledger writer exists but no EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows are mapped to C9 research signals",
        },
        {
            "source_id": "stage932_ctp_smoke_outputs",
            "source_family": "forward_capture_smoke",
            "evidence_path": str(BACKTEST_OUTPUT_DIR),
            "row_count": int(stage932[["order_rows", "trade_rows", "tick_rows"]].sum().sum()) if not stage932.empty else 0,
            "code_or_schema_ready": 1,
            "format_sample_ready": format_stage932,
            "valid_research_sample_count": valid_stage932,
            "rule_research_allowed": 0,
            "blocking_reason": "existing rows are dry-run/read-only or unlinked/mismatched; useful for schema inspection only",
        },
        {
            "source_id": "stage591_bridge_submit_adapter_dry_run",
            "source_family": "adapter_contract",
            "evidence_path": str(STAGE591_SUBMIT_PLAN),
            "row_count": len(submit_plan),
            "code_or_schema_ready": 1,
            "format_sample_ready": int(len(submit_plan) > 0),
            "valid_research_sample_count": int(pd.to_numeric(submit_plan.get("real_submit_allowed", 0), errors="coerce").fillna(0).sum()) if not submit_plan.empty else 0,
            "rule_research_allowed": 0,
            "blocking_reason": "dry-run payload contract only; no real vt_orderid returned by MainEngine.send_order",
        },
        {
            "source_id": "stage587_live_tca_bridge_dry_run",
            "source_family": "tca_contract",
            "evidence_path": str(STAGE587_LIVE_TCA),
            "row_count": len(live_tca),
            "code_or_schema_ready": 1,
            "format_sample_ready": int(len(live_tca) > 0),
            "valid_research_sample_count": int(pd.to_numeric(live_tca.get("valid_live_tca_sample", 0), errors="coerce").fillna(0).sum()) if not live_tca.empty else 0,
            "rule_research_allowed": 0,
            "blocking_reason": "TCA ledger is dry-run; valid_live_tca_sample count is zero",
        },
        {
            "source_id": "stage605_live_context_contract_adapter_audit",
            "source_family": "adapter_contract",
            "evidence_path": str(STAGE605_GATES),
            "row_count": len(stage605_gates),
            "code_or_schema_ready": 1,
            "format_sample_ready": 1,
            "valid_research_sample_count": int(pd.to_numeric(stage605_gates.get("passed", 0), errors="coerce").fillna(0).sum()) if not stage605_gates.empty else 0,
            "rule_research_allowed": 0,
            "blocking_reason": "source primitives exist, but fresh live context/vt_orderid/event join still missing",
        },
        {
            "source_id": "stage615_event_tca_reducer_contract",
            "source_family": "reducer_contract",
            "evidence_path": str(STAGE615_WRITER_CONTRACT),
            "row_count": len(writer_contract),
            "code_or_schema_ready": 1,
            "format_sample_ready": int(len(writer_contract) > 0),
            "valid_research_sample_count": 0,
            "rule_research_allowed": 0,
            "blocking_reason": "writer contract/synthetic samples only; no natural C9-linked event replay",
        },
        {
            "source_id": "stage110_route_summary",
            "source_family": "data_contract_audit",
            "evidence_path": str(STAGE110_SUMMARY_IN),
            "row_count": int(s110["asset_count"]),
            "code_or_schema_ready": 1,
            "format_sample_ready": int(s110["tca_or_forward_watch_only_asset_count"]),
            "valid_research_sample_count": int(s110["rule_usable_asset_count"]),
            "rule_research_allowed": 0,
            "blocking_reason": "Stage110 already found no rule-usable data asset",
        },
    ]
    return pd.DataFrame(rows)


def _field_contract() -> pd.DataFrame:
    rows = [
        {
            "field_group": "manifest",
            "field_name": "raw_file/raw_sha256/schema_hash/source_license/query_params/timezone/calendar_version",
            "required_for": "all_imported_data",
            "acceptance_rule": "100% non-empty and immutable before feature binding",
            "current_state": "missing_for_rule_replay",
            "pass_now": 0,
        },
        {
            "field_group": "historical_quote_depth",
            "field_name": "exchange_timestamp, receive_timestamp, bid_price_1..5, ask_price_1..5, bid_volume_1..5, ask_volume_1..5",
            "required_for": "authorized quote/depth replay",
            "acceptance_rule": ">=95% timestamp-ready C9 order-window coverage; 100% selected right-tail/bottom-loss coverage",
            "current_state": "absent_locally",
            "pass_now": 0,
        },
        {
            "field_group": "historical_quote_depth",
            "field_name": "last_price, trade_volume_delta, turnover_delta, open_interest, limit_up, limit_down",
            "required_for": "arrival/impact/TCA and event ordering",
            "acceptance_rule": "same source as quote/depth and monotonic point-in-time timestamps",
            "current_state": "absent_locally",
            "pass_now": 0,
        },
        {
            "field_group": "execution_replay",
            "field_name": "bridge_signal_id, order_reference, exact returned vt_orderid",
            "required_for": "strategy signal to broker event join",
            "acceptance_rule": "no synthetic vt_orderid; all submitted orders map signal -> reference -> vt_orderid",
            "current_state": "dry-run contracts exist; no valid live/replay mapping",
            "pass_now": 0,
        },
        {
            "field_group": "execution_replay",
            "field_name": "EVENT_ORDER status lifecycle and timestamps",
            "required_for": "order state replay",
            "acceptance_rule": "status rows linked by vt_orderid and ordered by receive time",
            "current_state": "only unlinked/dry-run/read-only rows available",
            "pass_now": 0,
        },
        {
            "field_group": "execution_replay",
            "field_name": "EVENT_TRADE fills: fill_first_at, fill_last_at, avg_fill_price, filled/unfilled/cancelled volume, commission",
            "required_for": "fill quality and realized slippage",
            "acceptance_rule": "all fills link to vt_orderid and reconcile to final order status",
            "current_state": "no C9-linked natural fill samples",
            "pass_now": 0,
        },
        {
            "field_group": "context",
            "field_name": "account_equity_before, margin_before, position_before, contract size/pricetick/min_volume",
            "required_for": "risk denominator and pre-submit eligibility",
            "acceptance_rule": "fresh snapshot within configured age and tied to the same submit intent",
            "current_state": "contracts/audits exist, but not joined to real C9 submit events",
            "pass_now": 0,
        },
        {
            "field_group": "right_tail_gate",
            "field_name": "right-tail and bottom-loss visual sample coverage",
            "required_for": "anti-overfit promotion gate",
            "acceptance_rule": "same-source data covers all selected right-tail/bottom-loss windows before rule design",
            "current_state": "no same-source data asset, so gate cannot run",
            "pass_now": 0,
        },
    ]
    return pd.DataFrame(rows)


def _gate_matrix(evidence: pd.DataFrame, stage932: pd.DataFrame, field_contract: pd.DataFrame) -> pd.DataFrame:
    valid_stage932 = int(stage932.get("valid_research_sample", pd.Series(dtype=int)).sum()) if not stage932.empty else 0
    format_stage932 = int(stage932.get("format_sample_only", pd.Series(dtype=int)).sum()) if not stage932.empty else 0
    live_ledger_rows = _count_ndjson_rows(LIVE_EXECUTION_LEDGER)
    rows = [
        {
            "gate_id": "licensed_historical_quote_depth_imported",
            "observed": "0",
            "required": "nonzero licensed quote/depth/orderflow archive with raw provenance",
            "pass_now": 0,
            "severity": "hard",
        },
        {
            "gate_id": "broker_or_production_execution_replay_imported",
            "observed": str(live_ledger_rows),
            "required": "mapped signal/reference/vt_orderid + EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows",
            "pass_now": 0,
            "severity": "hard",
        },
        {
            "gate_id": "stage932_format_sample_not_strategy_sample",
            "observed": f"format={format_stage932}; valid={valid_stage932}",
            "required": "valid linked non-dry-run submit/fill/tick sample",
            "pass_now": 0,
            "severity": "hard",
        },
        {
            "gate_id": "field_contract_all_pass",
            "observed": f"{int(field_contract['pass_now'].sum())}/{len(field_contract)}",
            "required": f"{len(field_contract)}/{len(field_contract)}",
            "pass_now": 0,
            "severity": "hard",
        },
        {
            "gate_id": "any_source_rule_research_allowed",
            "observed": str(int(evidence["rule_research_allowed"].sum())),
            "required": ">=1",
            "pass_now": 0,
            "severity": "hard",
        },
    ]
    return pd.DataFrame(rows)


def _next_action_manifest() -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "action_id": "import_authorized_historical_quote_depth",
            "action_type": "data_import_or_procurement",
            "done_definition": "manifest plus raw files cover >=95% C9 timestamp-ready order windows and 100% selected right-tail/bottom-loss windows",
            "why": "only route that can reconstruct intrabar order book state without broker event dependence",
            "rule_research_allowed_after_done": 0,
        },
        {
            "priority": 2,
            "action_id": "export_or_capture_same_source_execution_replay",
            "action_type": "broker_or_production_replay",
            "done_definition": "bridge_signal_id -> order_reference -> exact vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK join with raw provenance",
            "why": "needed to test whether minute entry/exit logic survives actual broker statuses and fills",
            "rule_research_allowed_after_done": 0,
        },
        {
            "priority": 3,
            "action_id": "build_forward_capture_acceptance_harness",
            "action_type": "forward_watch",
            "done_definition": "fresh read-only tick/order/trade/account/position/contract rows with non-dry-run linkage and no synthetic vt_orderid",
            "why": "can accumulate OOS evidence, but cannot backfill historical research immediately",
            "rule_research_allowed_after_done": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(evidence: pd.DataFrame, stage932: pd.DataFrame, gate: pd.DataFrame, field_contract: pd.DataFrame) -> pd.DataFrame:
    s110 = _read_csv(STAGE110_SUMMARY_IN).iloc[0]
    stage932_rows = 0 if stage932.empty else int(stage932[["order_rows", "trade_rows", "tick_rows"]].sum().sum())
    stage932_valid = 0 if stage932.empty else int(stage932["valid_research_sample"].sum())
    stage932_format = 0 if stage932.empty else int(stage932["format_sample_only"].sum())
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": "stage111_intake_acceptance_built_no_rule_data_still_blocked",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "evidence_source_count": int(len(evidence)),
                "rule_allowed_source_count": int(evidence["rule_research_allowed"].sum()),
                "stage932_session_count": int(len(stage932)),
                "stage932_total_snapshot_rows": stage932_rows,
                "stage932_format_sample_only_count": stage932_format,
                "stage932_valid_research_sample_count": stage932_valid,
                "intake_gate_count": int(len(gate)),
                "intake_gate_pass_count": int(gate["pass_now"].sum()),
                "field_contract_count": int(len(field_contract)),
                "field_contract_pass_count": int(field_contract["pass_now"].sum()),
                "next_recommended_route": "import_authorized_quote_depth_or_same_source_execution_replay",
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(s110["end_equity"]),
                "total_return_pct": float(s110["total_return_pct"]),
                "max_drawdown_pct": float(s110["max_drawdown_pct"]),
                "sharpe": float(s110["sharpe"]),
                "total_slippage": float(s110["total_slippage"]),
                "total_trade_count": float(s110["total_trade_count"]),
                "closed_lot_win_rate_pct": float(s110["closed_lot_win_rate_pct"]),
                "max_broker10_margin_to_equity_pct": float(s110["max_broker10_margin_to_equity_pct"]),
            }
        ]
    )


def _plot_path(curve: pd.DataFrame, risk: pd.DataFrame) -> None:
    risk = risk.copy()
    risk["official_open_date"] = pd.to_datetime(risk["official_open_date"], errors="coerce").dt.normalize()
    risk = risk.drop(
        columns=[
            column
            for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]
            if column in risk.columns
        ]
    )
    points = _nearest_curve_points(curve, risk["official_open_date"]).reset_index(drop=True)
    risk = risk.sort_values("official_open_date").reset_index(drop=True)
    if len(risk) == len(points):
        risk = pd.concat(
            [risk, points[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]],
            axis=1,
        )
    selected = risk[risk["bottom_loss_visual"].eq(1) | risk["right_tail_visual"].eq(1) | risk["maxdd_context"].eq(1)]
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#111827", lw=1.2)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.0)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8)
    for label, group in selected.groupby("risk_route_label"):
        color = "#dc2626" if "blocked" in str(label) else "#0f766e"
        size = np.where(group["bottom_loss_visual"].eq(1), 82, 42)
        edge = np.where(group["right_tail_visual"].eq(1), "#111827", "white")
        for ax, column, scale in [
            (axes[0], "account_equity", 1_000_000),
            (axes[1], "drawdown_pct", 1),
            (axes[2], "broker10_margin_to_equity_pct", 1),
        ]:
            ax.scatter(
                group["official_open_date"],
                group[column] / scale,
                s=size,
                c=color,
                edgecolors=edge,
                linewidths=0.6,
                alpha=0.82,
                label=label if ax is axes[0] else None,
            )
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_title("Stage111 official path: intake gates still block all rule research routes")
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_chart(gate: pd.DataFrame) -> None:
    data = gate.copy()
    data["blocked"] = 1 - pd.to_numeric(data["pass_now"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = np.where(data["blocked"].eq(1), "#dc2626", "#16a34a")
    ax.barh(data["gate_id"], data["blocked"], color=colors, alpha=0.86)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("blocked now")
    ax.set_title("Stage111 hard intake gates before rule research; red means blocked")
    for y, row in enumerate(data.itertuples(index=False)):
        ax.text(0.03, y, str(row.observed), color="white", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_stage932_chart(stage932: pd.DataFrame) -> None:
    if stage932.empty:
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.text(0.5, 0.5, "No Stage932 smoke summaries found", ha="center", va="center")
        ax.axis("off")
        fig.savefig(STAGE932_CHART_OUT, dpi=160)
        plt.close(fig)
        return
    data = stage932.sort_values("generated_at").tail(10).copy()
    labels = data["run_id"].astype(str)
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x - 0.25, data["order_rows"], width=0.25, label="order rows", color="#64748b")
    ax.bar(x, data["trade_rows"], width=0.25, label="trade rows", color="#0f766e")
    ax.bar(x + 0.25, data["tick_rows"], width=0.25, label="tick rows", color="#0369a1")
    ax.scatter(x, data["valid_research_sample"] * (data[["order_rows", "trade_rows", "tick_rows"]].max(axis=1) + 1), c="#dc2626", label="valid sample gate", zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel("rows")
    ax.set_title("Stage111 Stage932 smoke rows exist, but valid linked research samples remain zero")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(STAGE932_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_field_chart(field_contract: pd.DataFrame) -> None:
    data = field_contract.copy()
    data["blocked"] = 1 - pd.to_numeric(data["pass_now"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(12, max(4.5, 0.48 * len(data))))
    colors = np.where(data["blocked"].eq(1), "#dc2626", "#16a34a")
    ax.barh(data["field_group"] + " / " + data["required_for"], data["blocked"], color=colors, alpha=0.86)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("blocked now")
    ax.set_title("Stage111 required field groups for rule-ready intake; red means missing")
    for y, row in enumerate(data.itertuples(index=False)):
        ax.text(0.03, y, str(row.current_state), color="white", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIELD_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    evidence: pd.DataFrame,
    stage932: pd.DataFrame,
    gate: pd.DataFrame,
    field_contract: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage111 execution replay intake acceptance",
        "",
        "## Decision",
        "",
        f"- decision: `{row['decision']}`",
        "- nature: read-only intake acceptance harness; no strategy rule, no true engine, no A/B, no CTP connection, no order API.",
        "- question: after Stage110, can existing Stage932/591/587/605/615 artifacts be accepted as rule-ready execution replay evidence?",
        "",
        "## Baseline Path",
        "",
        f"- end equity: `{row['end_equity']:,.2f}`",
        f"- total return: `{row['total_return_pct']:.4f}%`",
        f"- max drawdown: `{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe: `{row['sharpe']:.4f}`",
        f"- total slippage: `{row['total_slippage']:,.0f}`",
        f"- total trade count: `{row['total_trade_count']:.0f}`",
        f"- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## Key Metrics",
        "",
        _md_table(summary),
        "",
        "## Evidence Sources",
        "",
        _md_table(evidence, max_rows=30),
        "",
        "## Stage932 Smoke Audit",
        "",
        _md_table(
            stage932[
                [
                    "run_id",
                    "mode",
                    "status",
                    "requested_vt_symbol",
                    "order_rows",
                    "trade_rows",
                    "tick_rows",
                    "order_vt_symbols",
                    "trade_vt_symbols",
                    "valid_research_sample",
                    "blockers",
                ]
            ]
            if not stage932.empty
            else stage932,
            max_rows=20,
        ),
        "",
        "## Intake Gates",
        "",
        _md_table(gate, max_rows=20),
        "",
        "## Field Contract",
        "",
        _md_table(field_contract, max_rows=30),
        "",
        "## Next Action Manifest",
        "",
        _md_table(next_action, max_rows=10),
        "",
        "## Visual Outputs",
        "",
        f"- official path intake blockers: `{PATH_CHART_OUT}`",
        f"- intake gate chart: `{GATE_CHART_OUT}`",
        f"- Stage932 smoke linkage chart: `{STAGE932_CHART_OUT}`",
        f"- field contract chart: `{FIELD_CHART_OUT}`",
        "",
        "## Judgment",
        "",
        (
            "Stage932 proves some callback/snapshot formats can exist, but the available samples are not accepted as "
            "research evidence because they are dry-run/read-only, have no order API call, no exact returned vt_orderid in "
            "the summary, and the non-empty order/trade rows are not linked to the requested submit reference. Stage591/587/"
            "605/615 remain useful contracts, not data. The next useful work is import/procurement or forward-capture "
            "acceptance, not a new minute-OHLC rule."
        ),
        "",
    ]
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    risk = _read_csv(STAGE108_RISK_IN)
    stage932 = _audit_stage932()
    evidence = _evidence_sources(stage932)
    field_contract = _field_contract()
    gate = _gate_matrix(evidence, stage932, field_contract)
    next_action = _next_action_manifest()
    summary = _summary(evidence, stage932, gate, field_contract)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(evidence, EVIDENCE_OUT)
    _write_csv(stage932, STAGE932_AUDIT_OUT)
    _write_csv(gate, GATE_MATRIX_OUT)
    _write_csv(field_contract, FIELD_CONTRACT_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_path(curve, risk)
    _plot_gate_chart(gate)
    _plot_stage932_chart(stage932)
    _plot_field_chart(field_contract)
    _write_report(summary, evidence, stage932, gate, field_contract, next_action)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": str(SUMMARY_OUT),
        "report_path": str(REPORT_OUT),
        "evidence_sources_path": str(EVIDENCE_OUT),
        "stage932_audit_path": str(STAGE932_AUDIT_OUT),
        "intake_gate_matrix_path": str(GATE_MATRIX_OUT),
        "field_contract_path": str(FIELD_CONTRACT_OUT),
        "next_action_manifest_path": str(NEXT_ACTION_OUT),
        "charts": [str(PATH_CHART_OUT), str(GATE_CHART_OUT), str(STAGE932_CHART_OUT), str(FIELD_CHART_OUT)],
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

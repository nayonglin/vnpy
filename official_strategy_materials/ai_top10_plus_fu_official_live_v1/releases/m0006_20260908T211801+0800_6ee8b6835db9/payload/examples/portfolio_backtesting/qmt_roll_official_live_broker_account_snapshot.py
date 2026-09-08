"""Read-only, generation-bound broker funds; never import or connect a CTP API."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qmt_roll_official_live_late_retry_fill import validate_readonly_query_bundle


ACCOUNT_FIELDS = ("Balance", "Available", "CurrMargin", "FrozenMargin", "FrozenCash", "FrozenCommission")
QUERY_NAMES = ("orders", "trades", "positions", "account", "contracts")
TERMINAL_ORDER_STATUSES = frozenset({
    "全部成交", "已撤销", "拒单", "all_traded", "alltraded", "cancelled", "rejected",
    "status.alltraded", "status.cancelled", "status.rejected",
})


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("broker_sizing_number_invalid")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError("broker_sizing_number_invalid") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError("broker_sizing_number_invalid")
    return number


def _sum(values: Any) -> float:
    try:
        return _number(math.fsum(values))
    except OverflowError:
        raise ValueError("broker_sizing_sum_overflow") from None


def _fingerprint(broker: Any, account: Any) -> str:
    if not isinstance(broker, str) or not isinstance(account, str) or not broker.strip() or not account.strip():
        raise ValueError("broker_sizing_raw_account_identity_missing")
    return hashlib.sha256(f"{broker.strip()}\0{account.strip()}".encode()).hexdigest()


def _product_symbol(symbol: Any, exchange: Any) -> str:
    match = re.fullmatch(r"([A-Za-z]+)[0-9]{3,4}", str(symbol))
    if not match or exchange not in {"CZCE", "CFFEX", "SHFE", "INE", "DCE", "GFEX"}:
        raise ValueError("broker_sizing_product_identity_invalid")
    product = match.group(1)
    product = product.upper() if exchange in {"CZCE", "CFFEX"} else product.lower()
    return f"{product}.{exchange}"


def broker_sizing_sha256(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _context(summary: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    bundle = summary["broker_query_bundle"]
    if bundle.get("schema_version") != 2 or bundle.get("complete") is not True:
        raise ValueError("broker_sizing_complete_v2_bundle_required")
    account = bundle["account"]
    fingerprint = account["account_fingerprint"]
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("broker_sizing_account_fingerprint_invalid")
    if any(account.get(key) is not True for key in ("login_account_match", "response_account_match", "trading_account_response_match")):
        raise ValueError("broker_sizing_account_binding_invalid")
    connection = bundle["snapshot_connection_generation"]
    lifecycle = summary["connection_lifecycle"]
    if (not connection or bundle.get("full_snapshot_current_generation") is not True
            or lifecycle.get("current_connection_generation") != connection
            or lifecycle.get("readiness_generation") != connection):
        raise ValueError("broker_sizing_connection_generation_invalid")
    for name in ("settlement", *QUERY_NAMES):
        if (bundle["snapshot_connection_generations"].get(name) != connection
                or lifecycle["snapshot_connection_generations"].get(name) != connection):
            raise ValueError("broker_sizing_snapshot_generation_mismatch")
    queries = bundle["queries"]
    reqids = []
    for name in QUERY_NAMES:
        query = queries[name]
        reqid = query.get("reqid")
        if (type(reqid) is not int or reqid <= 0 or query.get("complete") is not True
                or query.get("last_seen") is not True or query.get("request_sent") is not True
                or type(query.get("error_rows")) is not int or query["error_rows"] != 0
                or type(query.get("request_return_code")) is not int or query["request_return_code"] != 0
                or type(query.get("data_callback_count")) is not int or query["data_callback_count"] < 0
                or type(query.get("callback_count")) is not int
                or query["callback_count"] < max(1, query["data_callback_count"])
                or query.get("connection_generation") != connection):
            raise ValueError(f"broker_sizing_{name}_query_invalid")
        reqids.append(reqid)
    if len(set(reqids)) != len(reqids) or queries["account"]["data_callback_count"] != 1:
        raise ValueError("broker_sizing_unique_cny_account_query_required")
    return bundle, fingerprint, connection


def build_broker_account_snapshot(
    readonly_summary: dict[str, Any], raw_accounts: list[dict[str, Any]], raw_positions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Consume only Stage174's frozen, reqid-filtered rows, not EVENT_ACCOUNT."""
    try:
        bundle, fingerprint, connection = _context(readonly_summary)
        if len(raw_accounts) != 1 or raw_accounts[0].get("CurrencyID") != "CNY":
            raise ValueError("broker_sizing_unique_cny_account_required")
        account = raw_accounts[0]
        if _fingerprint(account.get("BrokerID"), account.get("AccountID")) != fingerprint:
            raise ValueError("broker_sizing_raw_account_mismatch")
        if len(raw_positions) != bundle["queries"]["positions"]["data_callback_count"]:
            raise ValueError("broker_sizing_position_callback_count_mismatch")
        values = {name: _number(account.get(name)) for name in ACCOUNT_FIELDS}
        if values["Balance"] <= 0:
            raise ValueError("broker_sizing_equity_not_positive")
        margin_rows = []
        product_values: dict[str, list[float]] = {}
        for row in raw_positions:
            if _fingerprint(row.get("BrokerID"), row.get("InvestorID")) != fingerprint:
                raise ValueError("broker_sizing_raw_position_account_mismatch")
            product = _product_symbol(row.get("InstrumentID"), row.get("ExchangeID"))
            margin = _number(row.get("UseMargin"))
            margin_rows.append({"symbol": row["InstrumentID"], "exchange": row["ExchangeID"], "use_margin": margin})
            product_values.setdefault(product, []).append(margin)
        return {
            "schema_version": 1, "complete": True, "currency": "CNY",
            "generation_uuid": bundle["generation_uuid"], "generated_at": bundle["generated_at"],
            "account_fingerprint": fingerprint, "connection_generation": connection,
            "account_query_reqid": bundle["queries"]["account"]["reqid"],
            "position_query_reqid": bundle["queries"]["positions"]["reqid"],
            "account_row_count": 1, "position_raw_row_count": len(raw_positions),
            "equity": values["Balance"], "available": values["Available"], "margin": values["CurrMargin"],
            "frozen": _sum(values[name] for name in ("FrozenMargin", "FrozenCash", "FrozenCommission")),
            "product_margin": {product: _sum(margins) for product, margins in sorted(product_values.items())},
            "account_values": values, "position_margin_rows": margin_rows,
        }
    except (KeyError, TypeError, AttributeError):
        raise ValueError("broker_sizing_source_metadata_missing") from None


def _json_object(payload: bytes) -> dict[str, Any]:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("broker_sizing_duplicate_json_key")
            result[key] = value
        return result

    result = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_pairs)
    if not isinstance(result, dict):
        raise ValueError("broker_sizing_json_object_required")
    return result


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("broker_sizing_timestamp_invalid")
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("broker_sizing_timestamp_timezone_required")
    return timestamp


def load_broker_account_snapshot(
    readonly_summary_path: Path, bundle_manifest_path: Path, *, now: datetime, max_age_seconds: float = 300,
) -> dict:
    """Fail closed unless local funds and all three artifacts share one fresh v2 bundle.

    Naive ``now`` uses Asia/Shanghai, matching the existing execution callers.
    Artifact bytes are hashed and parsed from the same read. No legacy accounts
    CSV, broker credentials, network, or production state is consulted.
    """
    try:
        limit = _number(max_age_seconds)
        if not isinstance(now, datetime):
            raise ValueError("broker_sizing_now_invalid")
        if now.tzinfo is None:
            now = now.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        summary_bytes = readonly_summary_path.read_bytes()
        manifest_bytes = bundle_manifest_path.read_bytes()
        summary = _json_object(summary_bytes)
        manifest = _json_object(manifest_bytes)
        bundle, fingerprint, connection = _context(summary)
        if manifest.get("queries") != bundle["queries"] or manifest.get("account") != bundle["account"]:
            raise ValueError("broker_sizing_manifest_query_or_account_mismatch")
        sizing = summary["broker_sizing"]
        if (not isinstance(sizing, dict) or sizing.get("complete") is not True
                or sizing.get("schema_version") != 1 or sizing != manifest.get("broker_sizing")
                or broker_sizing_sha256(sizing) != manifest.get("broker_sizing_sha256")
                or manifest.get("broker_sizing_sha256") != bundle.get("broker_sizing_sha256")):
            raise ValueError("broker_sizing_binding_or_hash_mismatch")
        if (sizing.get("generation_uuid") != bundle.get("generation_uuid")
                or sizing.get("generated_at") != bundle.get("generated_at")
                or sizing.get("account_fingerprint") != fingerprint
                or sizing.get("connection_generation") != connection
                or sizing.get("currency") != "CNY" or sizing.get("account_row_count") != 1
                or sizing.get("account_query_reqid") != bundle["queries"]["account"]["reqid"]
                or sizing.get("position_query_reqid") != bundle["queries"]["positions"]["reqid"]):
            raise ValueError("broker_sizing_query_identity_mismatch")
        if (Path(manifest["summary_binding"]["path"]).resolve() != readonly_summary_path.resolve()
                or Path(bundle["manifest_path"]).resolve() != bundle_manifest_path.resolve()):
            raise ValueError("broker_sizing_bundle_path_mismatch")
        generated = _time(sizing["generated_at"])
        if not 0 <= (now - generated).total_seconds() <= limit:
            raise ValueError("broker_sizing_snapshot_stale_or_future")
        for query in bundle["queries"].values():
            sent = _time(query["request_sent_at"])
            completed = _time(query["completed_at"])
            if not sent <= completed <= generated or not 0 <= (now - sent).total_seconds() <= limit:
                raise ValueError("broker_sizing_query_stale_or_future")

        artifacts = {}
        rows_by_name = {}
        artifact_bytes = {}
        for name in ("orders", "trades", "positions"):
            reference = manifest["artifacts"][name]
            if reference != bundle["artifacts"][name]:
                raise ValueError("broker_sizing_artifact_reference_mismatch")
            path = Path(reference["path"])
            if not path.is_absolute():
                raise ValueError("broker_sizing_artifact_path_not_absolute")
            payload = path.read_bytes()
            artifact_bytes[path] = payload
            reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
            rows = list(reader)
            rows_by_name[name] = rows
            if reader.fieldnames and len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("broker_sizing_duplicate_csv_column")
            if any(None in row or any(value is None for value in row.values()) for row in rows):
                raise ValueError("broker_sizing_malformed_csv_row")
            if any(row.get("query_generation_uuid") != sizing["generation_uuid"] for row in rows):
                raise ValueError("broker_sizing_artifact_row_generation_mismatch")
            artifacts[name] = {
                "row_count": len(rows), "sha256": hashlib.sha256(payload).hexdigest(),
                "generation_uuids": sorted({row.get("query_generation_uuid", "") for row in rows}),
                "account_fingerprints": sorted({_fingerprint(row.get("broker_id"), row.get("account_id")) for row in rows}),
            }
        trades = rows_by_name["trades"]
        artifacts["trades"]["order_mapping_complete"] = all(
            row.get("order_mapping_complete") == "1" and bool(row.get("vt_orderid")) for row in trades
        )
        artifacts["trades"]["stable_trade_identity_complete"] = all(
            row.get("stable_trade_identity_complete") == "1" and bool(row.get("broker_trade_identity")) for row in trades
        )
        valid, reason, _, _ = validate_readonly_query_bundle(
            readonly_summary=summary, bundle_manifest=manifest, bundle_evidence={"artifacts": artifacts},
        )
        if not valid:
            raise ValueError(reason)
        if any(row.get("status", "").strip().lower() not in TERMINAL_ORDER_STATUSES for row in rows_by_name["orders"]):
            raise ValueError("broker_sizing_active_or_unknown_orders")

        values = {name: _number(sizing["account_values"][name]) for name in ACCOUNT_FIELDS}
        expected_money = {"equity": values["Balance"], "available": values["Available"], "margin": values["CurrMargin"],
                          "frozen": _sum(values[name] for name in ("FrozenMargin", "FrozenCash", "FrozenCommission"))}
        if values["Balance"] <= 0 or any(_number(sizing[key]) != value for key, value in expected_money.items()):
            raise ValueError("broker_sizing_money_fields_mismatch")
        margin_rows = sizing["position_margin_rows"]
        if (not isinstance(margin_rows, list) or len(margin_rows) != sizing["position_raw_row_count"]
                or len(margin_rows) != bundle["queries"]["positions"]["data_callback_count"]):
            raise ValueError("broker_sizing_position_margin_count_mismatch")
        product_values: dict[str, list[float]] = {}
        for row in margin_rows:
            product = _product_symbol(row["symbol"], row["exchange"])
            product_values.setdefault(product, []).append(_number(row["use_margin"]))
        product_margin = {product: _sum(margins) for product, margins in product_values.items()}
        if (not isinstance(sizing["product_margin"], dict)
                or {key: _number(value) for key, value in sizing["product_margin"].items()} != product_margin):
            raise ValueError("broker_sizing_product_margin_mismatch")
        if (readonly_summary_path.read_bytes() != summary_bytes or bundle_manifest_path.read_bytes() != manifest_bytes
                or any(path.read_bytes() != payload for path, payload in artifact_bytes.items())):
            raise ValueError("broker_sizing_bundle_changed_during_read")
        return {**sizing, **expected_money, "product_margin": product_margin,
                **rows_by_name,
                "query_started_at": min(_time(query["request_sent_at"]) for query in bundle["queries"].values()).isoformat(),
                "artifacts": manifest["artifacts"], "bundle_evidence": {"artifacts": artifacts},
                "broker_sizing_sha256": manifest["broker_sizing_sha256"]}
    except (OSError, UnicodeError, KeyError, TypeError, AttributeError, OverflowError, csv.Error):
        raise ValueError("broker_sizing_artifact_or_metadata_invalid") from None

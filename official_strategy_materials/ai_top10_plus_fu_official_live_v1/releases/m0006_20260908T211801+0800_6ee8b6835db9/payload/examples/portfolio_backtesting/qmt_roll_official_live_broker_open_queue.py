"""Pure budget release evidence for sent opens; never reconcile or requeue spool rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import re
from typing import Any

from qmt_roll_official_live_broker_account_snapshot import (
    TERMINAL_ORDER_STATUSES,
    broker_sizing_sha256,
    _fingerprint,
    _number,
    _time,
)
from qmt_roll_official_live_execution_ledger import (
    _ledger_integrity_blocker,
    _legacy_alias_fingerprints,
    _recovery_event_matches_lease,
    _record_checksum,
    intent_fingerprint,
)
from qmt_roll_official_live_late_retry_fill import _normalize_direction, _normalize_offset


def _epoch_ns(timestamp: datetime) -> int:
    delta = timestamp - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000


def evaluate_sent_open_budget_release(
    *,
    sent_intent: Mapping[str, Any],
    broker_snapshot: Mapping[str, Any],
    execution_ledger_rows: Sequence[Mapping[str, Any]],
    now: datetime,
    max_age_seconds: float = 300,
) -> dict[str, Any]:
    """Assess one ``asdict(SpoolIntent)`` using freshly loaded, validated evidence.

    Pass the unmodified result of ``load_broker_account_snapshot`` (including
    orders/positions/trades) and ``read_execution_ledger`` rows. The caller
    retains every other queue blocker and sizes the next open from this same
    snapshot, not from refunded planned margin. A release applies only to this
    observation: do not persist it as reconciliation or permission to resend.
    """
    return _evaluate_sent_open_budget_release(
        sent_intent=sent_intent, broker_snapshot=broker_snapshot,
        execution_ledger_rows=execution_ledger_rows, now=now, max_age_seconds=max_age_seconds,
    )


def _legacy_sent_account_binding(
    sent_intent: Mapping[str, Any], account: str, ledger: list[dict[str, Any]],
    bound: list[dict[str, Any]], order_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(account, str) or not re.fullmatch(r"[0-9a-f]{64}", account):
        raise ValueError("legacy_account_fingerprint_invalid")
    sources = []
    payload = sent_intent["payload"]
    for name, mapping in (("payload", payload), ("order_request", payload["order_request"])):
        if "account_fingerprint" in mapping:
            if mapping["account_fingerprint"] != account:
                raise ValueError("legacy_account_binding_mismatch")
            sources.append(f"{name}.account_fingerprint")
    owned_checksums = set()
    for event in bound:
        if (event.get("spool_lease_owner") != sent_intent["lease_owner"]
                or event.get("spool_lease_token") != sent_intent["lease_token"]
                or event.get("intent_id") != sent_intent["intent_id"]):
            raise ValueError("legacy_ledger_ownership_mismatch")
        checksum = event.get("record_checksum")
        if not checksum or checksum != _record_checksum(event):
            raise ValueError("legacy_ledger_checksum_required")
        if event.get("vt_orderid") in order_ids:
            owned_checksums.add(checksum)
        if "account_fingerprint" in event:
            if event["account_fingerprint"] != account:
                raise ValueError("legacy_account_binding_mismatch")
            if event.get("event_type") == "reserved" or event.get("vt_orderid") in order_ids:
                sources.append(f"ledger:{checksum}:account_fingerprint")
    for event in ledger:
        if (event.get("vt_orderid") in order_ids
                and event.get("event_type") in {
                    "native_order_identity_persisted_before_insert", "send_order_returned", "submitted_to_ctp",
                }
                and event not in bound):
            raise ValueError("legacy_order_ownership_ambiguous")
    if not sources:
        raise ValueError("legacy_audit_migration_required:explicit_account_binding_missing")
    return {"prior_broker_sizing_present": False, "account_binding_sources": sorted(set(sources)),
            "owned_order_ledger_checksums": sorted(owned_checksums)}


def _evaluate_sent_open_budget_release(
    *,
    sent_intent: Mapping[str, Any],
    broker_snapshot: Mapping[str, Any],
    execution_ledger_rows: Sequence[Mapping[str, Any]],
    now: datetime,
    max_age_seconds: float = 300,
    allow_legacy_migration: bool = False,
) -> dict[str, Any]:
    try:
        if sent_intent["state"] != "sent" or sent_intent["intent_kind"] != "open":
            raise ValueError("sent_open_required")
        updated = sent_intent["updated_epoch_ns"]
        if type(updated) is not int or updated <= 0:
            raise ValueError("sent_timestamp_invalid")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now_timezone_required")
        generated = _time(broker_snapshot["generated_at"])
        started = _time(broker_snapshot["query_started_at"])
        age_limit = _number(max_age_seconds)
        if not started <= generated <= now or (now - started).total_seconds() > age_limit:
            raise ValueError("snapshot_stale_or_future")
        if _epoch_ns(started) <= updated:
            raise ValueError("snapshot_precedes_sent")
        if broker_snapshot["complete"] is not True or not broker_snapshot["generation_uuid"]:
            raise ValueError("snapshot_incomplete")
        for name in ("orders", "positions", "trades"):
            if not isinstance(broker_snapshot[name], list):
                raise ValueError("validated_snapshot_rows_required")

        payload = sent_intent["payload"]
        request = payload["order_request"]
        sizing = payload.get("broker_sizing", request.get("broker_sizing", {}))
        legacy = "broker_sizing" not in payload and "broker_sizing" not in request
        account = broker_snapshot["account_fingerprint"]
        if not (legacy and allow_legacy_migration) and (not account or sizing.get("account_fingerprint") != account):
            raise ValueError("account_binding_mismatch")
        if not legacy and request.get("broker_sizing", sizing).get("account_fingerprint") != account:
            raise ValueError("account_binding_mismatch")
        target_date = sent_intent["target_date"]
        if not target_date or payload["target_date"] != target_date or payload["intent_id"] != sent_intent["intent_id"]:
            raise ValueError("intent_identity_mismatch")
        fingerprint, normalized = intent_fingerprint(target_date, dict(payload), dict(request))
        if normalized["offset"] != "open":
            raise ValueError("sent_open_required")
        accepted = {fingerprint, *_legacy_alias_fingerprints(normalized)}
        owner, token = sent_intent["lease_owner"], sent_intent["lease_token"]
        if not owner or not token:
            raise ValueError("retained_lease_required")
        ledger = [dict(event) for event in execution_ledger_rows]
        integrity = _ledger_integrity_blocker(ledger)
        if integrity:
            raise ValueError(integrity)
        bound = []
        for event in ledger:
            if not _recovery_event_matches_lease(event, spool_lease_owner=owner, spool_lease_token=token):
                continue
            if event.get("target_date") != target_date or event.get("intent_fingerprint") not in accepted:
                raise ValueError("ledger_lease_identity_mismatch")
            bound.append(event)
        reservations = [index for index, event in enumerate(bound) if event.get("event_type") == "reserved"]
        if not reservations:
            raise ValueError("durable_reservation_missing")
        if legacy and len(reservations) != 1:
            raise ValueError("legacy_reservation_ambiguous")
        order_ids = set()
        for event in bound[reservations[-1] + 1:]:
            if event.get("event_type") in {
                "native_order_identity_persisted_before_insert", "send_order_returned", "submitted_to_ctp",
            }:
                order_id = event.get("vt_orderid")
                if not isinstance(order_id, str) or not order_id.strip():
                    raise ValueError("durable_order_identity_missing")
                order_ids.add(order_id)
        if not order_ids:
            raise ValueError("durable_order_identity_missing")
        migration = _legacy_sent_account_binding(sent_intent, account, ledger, bound, order_ids) if legacy else None

        for order_id in sorted(order_ids):
            matches = [row for row in broker_snapshot["orders"] if row.get("vt_orderid") == order_id]
            if len(matches) != 1:
                raise ValueError("broker_order_missing_or_ambiguous")
            order = matches[0]
            if (order.get("query_generation_uuid") != broker_snapshot["generation_uuid"]
                    or _fingerprint(order.get("broker_id"), order.get("account_id")) != account):
                raise ValueError("broker_order_account_or_generation_mismatch")
            if (str(order.get("vt_symbol", "")).upper() != str(normalized["vt_symbol"]).upper()
                    or _normalize_direction(order.get("direction")) != normalized["direction"]
                    or _normalize_offset(order.get("offset")) != "open"):
                raise ValueError("broker_order_contract_mismatch")
            status = str(order.get("status", "")).strip().lower()
            if status not in TERMINAL_ORDER_STATUSES:
                raise ValueError("broker_order_not_terminal")
            volume, traded = _number(order.get("volume")), _number(order.get("traded"))
            if volume <= 0 or not volume.is_integer() or not traded.is_integer() or traded > volume:
                raise ValueError("broker_order_volume_invalid")
            if status in {"全部成交", "all_traded", "alltraded", "status.alltraded"} and traded != volume:
                raise ValueError("broker_order_terminal_volume_mismatch")
        return {"budget_released": True, "blocker": "", "vt_orderids": sorted(order_ids),
                "intent_fingerprint": fingerprint, "generation_uuid": broker_snapshot["generation_uuid"],
                **({"migration": migration} if migration is not None else {})}
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "input_missing_or_invalid"
        return {"budget_released": False, "blocker": f"broker_sizing_sent_{reason}", "vt_orderids": []}


def build_sent_open_reconciliation_proof(
    *,
    sent_intent: Mapping[str, Any],
    broker_snapshot: Mapping[str, Any],
    execution_ledger_rows: Sequence[Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Bind terminal evidence to an immutable payload and its exact sent revision.

    Snapshot and ledger inputs must come from their validating local readers.
    No raw account identifiers or broker rows are persisted in this proof.
    Missing historical sizing is migratable only with a pre-existing explicit
    account fingerprint in the immutable payload/request or checksum-verified,
    exact-lease ledger evidence. Current snapshot identity alone is not adoption
    authority. Migration never reconstructs or edits the original sizing audit.
    """
    try:
        payload = sent_intent["payload"]
        request = payload["order_request"]
        release = _evaluate_sent_open_budget_release(
            sent_intent=sent_intent, broker_snapshot=broker_snapshot,
            execution_ledger_rows=execution_ledger_rows, now=now, allow_legacy_migration=True,
        )
        if not release["budget_released"]:
            raise ValueError(release["blocker"])
        if sent_intent["payload_sha256"] != broker_sizing_sha256(dict(payload)):
            raise ValueError("broker_sizing_sent_payload_hash_mismatch")
        revision = sent_intent["state_revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("broker_sizing_sent_state_revision_invalid")
        ledger = [dict(event) for event in execution_ledger_rows]
        for event in ledger:
            if event.get("record_checksum") and event["record_checksum"] != _record_checksum(event):
                raise ValueError("broker_sizing_sent_ledger_checksum_mismatch")
        hashes = {
            "broker_sizing_sha256": broker_snapshot["broker_sizing_sha256"],
            "ledger_checksum_sha256": ledger[-1]["record_checksum"],
            **{f"{name}_sha256": broker_snapshot["artifacts"][name]["sha256"]
               for name in ("orders", "positions", "trades")},
        }
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes.values()):
            raise ValueError("broker_sizing_sent_evidence_hash_invalid")
        proof = {
            "schema_version": 1, "kind": ("legacy_sent_open_broker_reconciliation_v1"
                                           if "migration" in release else "sent_open_broker_reconciliation_v1"),
            "intent_id": sent_intent["intent_id"], "target_date": sent_intent["target_date"],
            "payload_sha256": sent_intent["payload_sha256"], "sent_state_revision": revision,
            "sent_updated_epoch_ns": sent_intent["updated_epoch_ns"],
            "lease_owner": sent_intent["lease_owner"], "lease_token": sent_intent["lease_token"],
            "account_fingerprint": broker_snapshot["account_fingerprint"],
            "snapshot_generation_uuid": broker_snapshot["generation_uuid"],
            "snapshot_generated_at": broker_snapshot["generated_at"],
            "query_started_at": broker_snapshot["query_started_at"],
            "snapshot_sha256": broker_sizing_sha256(dict(broker_snapshot)),
            "vt_orderids": release["vt_orderids"], "ledger_fingerprint": release["intent_fingerprint"],
            "ledger_watermark": len(ledger), "ledger_snapshot_sha256": broker_sizing_sha256({"rows": ledger}),
            **hashes,
            **({"migration": release["migration"]} if "migration" in release else {}),
        }
        return {**proof, "proof_sha256": broker_sizing_sha256(proof)}
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError):
        raise ValueError("broker_sizing_sent_reconciliation_evidence_invalid") from None

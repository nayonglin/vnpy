from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from pathlib import Path
import tempfile
from typing import Any


SUBMIT_AUTHORIZATION_SCHEMA_VERSION = 3
SUBMIT_AUTHORIZATION_FILENAME = "stage179_submit_authorization.json"
_INTENT_SCOPES = {"all", "reduce_close_only"}
_INTENT_KINDS = {"open", "close"}
_SHA256_HEX = frozenset("0123456789abcdef")


def submit_authorization_path(output_root: str | Path) -> Path:
    return (
        Path(output_root).expanduser().resolve(strict=False)
        / SUBMIT_AUTHORIZATION_FILENAME
    )


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "record_digest"}
    return hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = path.expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


def _signed(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["record_digest"] = _canonical_digest(result)
    return result


def _normalized_authorized_intents(
    rows: Any,
) -> list[dict[str, str]]:
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError(
            "stage179_submit_authorization_authorized_intents_missing"
        )
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(
                "stage179_submit_authorization_authorized_intent_invalid"
            )
        intent_id = str(row.get("intent_id", "")).strip()
        payload_sha256 = str(row.get("payload_sha256", "")).strip().lower()
        intent_kind = str(row.get("intent_kind", "")).strip().lower()
        if not intent_id:
            raise ValueError(
                "stage179_submit_authorization_intent_id_missing"
            )
        if intent_id in seen:
            raise ValueError(
                "stage179_submit_authorization_authorized_intent_duplicate"
            )
        if (
            len(payload_sha256) != 64
            or any(character not in _SHA256_HEX for character in payload_sha256)
        ):
            raise ValueError(
                "stage179_submit_authorization_payload_sha256_invalid"
            )
        if intent_kind not in _INTENT_KINDS:
            raise ValueError(
                "stage179_submit_authorization_intent_kind_invalid"
            )
        seen.add(intent_id)
        normalized.append(
            {
                "intent_id": intent_id,
                "payload_sha256": payload_sha256,
                "intent_kind": intent_kind,
            }
        )
    return sorted(normalized, key=lambda item: item["intent_id"])


def publish_submit_authorization(
    *,
    path: str | Path,
    target_date: str,
    execution_profile: str,
    runtime_profile: str,
    order_scope: str,
    service_generation: str,
    connection_generation: str,
    cycle_id: str,
    intent_scope: str,
    authorized_intents: Any,
    issued_epoch_ns: int,
    expires_epoch_ns: int,
    controller_evidence: Mapping[str, Any],
    stage927_evidence: Mapping[str, Any],
    broker_gate_evidence: Mapping[str, Any],
    tick_watermark_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if intent_scope not in _INTENT_SCOPES:
        raise ValueError("stage179_submit_authorization_intent_scope_invalid")
    if int(expires_epoch_ns) <= int(issued_epoch_ns):
        raise ValueError("stage179_submit_authorization_expiry_invalid")
    required_strings = {
        "target_date": target_date,
        "execution_profile": execution_profile,
        "runtime_profile": runtime_profile,
        "order_scope": order_scope,
        "service_generation": service_generation,
        "connection_generation": connection_generation,
        "cycle_id": cycle_id,
    }
    if any(not str(value).strip() for value in required_strings.values()):
        raise ValueError("stage179_submit_authorization_identity_missing")
    evidence = {
        "controller_evidence": dict(controller_evidence),
        "stage927_evidence": dict(stage927_evidence),
        "broker_gate_evidence": dict(broker_gate_evidence),
        "tick_watermark_evidence": dict(tick_watermark_evidence),
    }
    if any(not value for value in evidence.values()):
        raise ValueError("stage179_submit_authorization_evidence_missing")
    normalized_intents = _normalized_authorized_intents(authorized_intents)
    if intent_scope == "reduce_close_only" and any(
        row["intent_kind"] != "close" for row in normalized_intents
    ):
        raise ValueError(
            "stage179_submit_authorization_reduce_close_scope_contains_open"
        )
    payload = _signed(
        {
            "schema_version": SUBMIT_AUTHORIZATION_SCHEMA_VERSION,
            "status": "authorized",
            **{key: str(value).strip() for key, value in required_strings.items()},
            "intent_scope": intent_scope,
            "authorized_intents": normalized_intents,
            "issued_epoch_ns": int(issued_epoch_ns),
            "expires_epoch_ns": int(expires_epoch_ns),
            **evidence,
        }
    )
    _atomic_write_json(Path(path), payload)
    return payload


def revoke_submit_authorization(
    path: str | Path,
    *,
    reason: str,
    revoked_epoch_ns: int,
) -> dict[str, Any]:
    authorization_path = Path(path).expanduser().resolve(strict=False)
    previous: dict[str, Any] = {}
    try:
        loaded = json.loads(authorization_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            previous = loaded
    except (OSError, ValueError, TypeError):
        pass
    payload = _signed(
        {
            key: value
            for key, value in previous.items()
            if key != "record_digest"
        }
        | {
            "schema_version": SUBMIT_AUTHORIZATION_SCHEMA_VERSION,
            "status": "revoked",
            "revocation_reason": str(reason),
            "revoked_epoch_ns": int(revoked_epoch_ns),
            "expires_epoch_ns": min(
                int(previous.get("expires_epoch_ns", revoked_epoch_ns)),
                int(revoked_epoch_ns),
            ),
        }
    )
    _atomic_write_json(authorization_path, payload)
    return payload


def read_submit_authorization(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def authorized_submit_intents(path: str | Path) -> dict[str, str]:
    """Return the exact immutable allow-list, or no authority on any defect."""

    payload = read_submit_authorization(path)
    if (
        payload.get("schema_version") != SUBMIT_AUTHORIZATION_SCHEMA_VERSION
        or payload.get("status") != "authorized"
    ):
        return {}
    digest = str(payload.get("record_digest", ""))
    if len(digest) != 64 or not hmac.compare_digest(
        digest,
        _canonical_digest(payload),
    ):
        return {}
    try:
        rows = _normalized_authorized_intents(payload.get("authorized_intents"))
    except ValueError:
        return {}
    return {row["intent_id"]: row["payload_sha256"] for row in rows}


def validate_submit_authorization(
    *,
    path: str | Path,
    target_date: str | None,
    execution_profile: str,
    runtime_profile: str,
    order_scope: str,
    service_generation: str,
    connection_generation: str,
    now_epoch_ns: int,
    intent_id: str | None = None,
    payload_sha256: str | None = None,
    intent_kind: str | None = None,
    child_offset: str | None = None,
) -> list[str]:
    payload = read_submit_authorization(path)
    if not payload:
        return ["stage179_submit_authorization_missing"]
    blockers: list[str] = []
    if payload.get("schema_version") != SUBMIT_AUTHORIZATION_SCHEMA_VERSION:
        blockers.append("stage179_submit_authorization_schema_invalid")
    digest = str(payload.get("record_digest", ""))
    if len(digest) != 64 or not hmac.compare_digest(digest, _canonical_digest(payload)):
        blockers.append("stage179_submit_authorization_digest_mismatch")
    if payload.get("status") != "authorized":
        blockers.append("stage179_submit_authorization_not_authorized")
    expected = {
        "execution_profile": execution_profile,
        "runtime_profile": runtime_profile,
        "order_scope": order_scope,
        "service_generation": service_generation,
        "connection_generation": connection_generation,
    }
    if target_date is not None:
        expected["target_date"] = target_date
    for key, value in expected.items():
        if str(payload.get(key, "")) != str(value):
            blockers.append(f"stage179_submit_authorization_{key}_mismatch")
    if int(payload.get("issued_epoch_ns", 0) or 0) <= 0:
        blockers.append("stage179_submit_authorization_issued_time_invalid")
    if int(now_epoch_ns) >= int(payload.get("expires_epoch_ns", 0) or 0):
        blockers.append("stage179_submit_authorization_expired")
    if not str(payload.get("cycle_id", "")).strip():
        blockers.append("stage179_submit_authorization_cycle_id_missing")
    authorized_rows: list[dict[str, str]] = []
    try:
        authorized_rows = _normalized_authorized_intents(
            payload.get("authorized_intents")
        )
    except ValueError as exc:
        blockers.append(str(exc))
    for evidence_key in (
        "controller_evidence",
        "stage927_evidence",
        "broker_gate_evidence",
        "tick_watermark_evidence",
    ):
        if not isinstance(payload.get(evidence_key), dict) or not payload[evidence_key]:
            blockers.append(f"stage179_submit_authorization_{evidence_key}_missing")
    scope = str(payload.get("intent_scope", ""))
    if scope not in _INTENT_SCOPES:
        blockers.append("stage179_submit_authorization_intent_scope_invalid")
    if scope == "reduce_close_only":
        if intent_kind is not None and str(intent_kind).lower() != "close":
            blockers.append("stage179_submit_authorization_reduce_close_only")
        if child_offset is not None and str(child_offset).lower() == "open":
            blockers.append("stage179_submit_authorization_reduce_close_only")
    if (intent_id is None) != (payload_sha256 is None):
        blockers.append(
            "stage179_submit_authorization_intent_identity_incomplete"
        )
    elif intent_id is not None and payload_sha256 is not None:
        normalized_intent_id = str(intent_id).strip()
        normalized_sha = str(payload_sha256).strip().lower()
        authorized = next(
            (
                row
                for row in authorized_rows
                if row["intent_id"] == normalized_intent_id
            ),
            None,
        )
        if authorized is None:
            blockers.append(
                "stage179_submit_authorization_intent_not_authorized"
            )
        else:
            if not hmac.compare_digest(
                authorized["payload_sha256"],
                normalized_sha,
            ):
                blockers.append(
                    "stage179_submit_authorization_payload_sha256_mismatch"
                )
            if (
                intent_kind is not None
                and authorized["intent_kind"]
                != str(intent_kind).strip().lower()
            ):
                blockers.append(
                    "stage179_submit_authorization_intent_kind_mismatch"
                )
    controller = payload.get("controller_evidence", {})
    stage927 = payload.get("stage927_evidence", {})
    broker = payload.get("broker_gate_evidence", {})
    tick = payload.get("tick_watermark_evidence", {})
    reduce_close_only = scope == "reduce_close_only"
    evidence_expiry_keys = [
        ("controller_evidence", controller),
        ("stage927_evidence", stage927),
    ]
    if not reduce_close_only:
        evidence_expiry_keys.append(("tick_watermark_evidence", tick))
    authorization_expires_epoch_ns = int(
        payload.get("expires_epoch_ns", 0) or 0
    )
    for evidence_name, evidence_payload in evidence_expiry_keys:
        evidence_expires_epoch_ns = int(
            evidence_payload.get("expires_epoch_ns", 0) or 0
        ) if isinstance(evidence_payload, dict) else 0
        if evidence_expires_epoch_ns <= 0:
            blockers.append(
                "stage179_submit_authorization_"
                f"{evidence_name}_expiry_missing"
            )
            continue
        if authorization_expires_epoch_ns > evidence_expires_epoch_ns:
            blockers.append(
                "stage179_submit_authorization_"
                f"exceeds_{evidence_name}_expiry"
            )
        if int(now_epoch_ns) >= evidence_expires_epoch_ns:
            blockers.append(
                "stage179_submit_authorization_"
                f"{evidence_name}_expired"
            )
    if isinstance(controller, dict):
        if target_date is not None and str(controller.get("target_date", "")) != str(
            target_date
        ):
            blockers.append(
                "stage179_submit_authorization_controller_target_date_mismatch"
            )
        if (
            not reduce_close_only
            and controller.get("controller_status")
            != "phase_d_controller_live_real_ready_no_submit_step"
        ):
            blockers.append(
                "stage179_submit_authorization_controller_not_ready"
            )
        if controller.get("stage905_executor_status") != "executor_dry_run_ready":
            blockers.append(
                "stage179_submit_authorization_stage905_executor_not_ready"
            )
        if int(controller.get("stage905_blocked_count", -1) or 0) != 0:
            blockers.append(
                "stage179_submit_authorization_stage905_blocked"
            )
        if int(controller.get("stage905_ready_count", 0) or 0) <= 0:
            blockers.append(
                "stage179_submit_authorization_no_ready_intent"
            )
    if (
        isinstance(stage927, dict)
        and not reduce_close_only
        and int(stage927.get("real_submit_permitted", 0) or 0) != 1
    ):
        blockers.append("stage179_submit_authorization_stage927_not_ready")
    if isinstance(broker, dict):
        if broker.get("status") != "ready":
            blockers.append("stage179_submit_authorization_broker_not_ready")
        if str(broker.get("service_generation", "")) != str(service_generation):
            blockers.append(
                "stage179_submit_authorization_broker_service_generation_mismatch"
            )
        if str(broker.get("connection_generation", "")) != str(
            connection_generation
        ):
            blockers.append(
                "stage179_submit_authorization_broker_connection_generation_mismatch"
            )
        broker_expires_epoch_ns = int(
            broker.get("expires_epoch_ns", 0) or 0
        )
        if broker_expires_epoch_ns <= 0:
            blockers.append(
                "stage179_submit_authorization_broker_readiness_expiry_missing"
            )
        else:
            if int(payload.get("expires_epoch_ns", 0) or 0) > broker_expires_epoch_ns:
                blockers.append(
                    "stage179_submit_authorization_exceeds_broker_readiness_expiry"
                )
            if int(now_epoch_ns) >= broker_expires_epoch_ns:
                blockers.append(
                    "stage179_submit_authorization_broker_readiness_expired"
                )
    if (
        isinstance(tick, dict)
        and not reduce_close_only
        and int(tick.get("all_symbols_ready", 0) or 0) != 1
    ):
        blockers.append("stage179_submit_authorization_tick_gate_not_ready")
    return list(dict.fromkeys(blockers))


__all__ = [
    "SUBMIT_AUTHORIZATION_FILENAME",
    "SUBMIT_AUTHORIZATION_SCHEMA_VERSION",
    "authorized_submit_intents",
    "publish_submit_authorization",
    "read_submit_authorization",
    "revoke_submit_authorization",
    "submit_authorization_path",
    "validate_submit_authorization",
]

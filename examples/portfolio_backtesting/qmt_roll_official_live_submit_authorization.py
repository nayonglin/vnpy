from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Mapping
from pathlib import Path
import tempfile
from typing import Any


SUBMIT_AUTHORIZATION_SCHEMA_VERSION = 4
SUBMIT_AUTHORIZATION_FILENAME = "stage179_submit_authorization.json"
_AUTHORIZATION_LANES = {
    "slow_controller",
    "persistent_intraday_fast",
    "session_initial_open",
}
_INTENT_SCOPES = {
    "all",
    "reduce_close_only",
    "retry_open_only",
    "initial_open_only",
}
_INTENT_KINDS = {"open", "close"}
_SHA256_HEX = frozenset("0123456789abcdef")
_EXACT_TEXT_FIELDS = (
    "source",
    "intent_role",
    "trace_id",
    "state_generation",
    "position_epoch_id",
    "root_position_id",
    "position_cycle_id",
)
_EXACT_INT_FIELDS = (
    "spool_sequence",
    "state_revision",
    "deadline_epoch_ns",
)
_FAST_CLOSE_SOURCE = "stage904_c9_intraday_close"
_FAST_CLOSE_ROLES = {
    "c9_initial_stop_close",
    "c9_retry_failed_stop_close",
}
_FAST_RETRY_OPEN_SOURCE = "stage904_c9_intraday_retry_open"
_FAST_RETRY_OPEN_ROLE = "c9_retry_open_once"
_INITIAL_OPEN_SOURCE = "stage901_pending_order"
_INITIAL_OPEN_ROLE = "c9_initial_open"


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


def _is_sha256(value: Any) -> bool:
    text = str(value).strip().lower()
    return bool(
        len(text) == 64
        and all(character in _SHA256_HEX for character in text)
    )


def _optional_digest(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip().lower()
    if text and not _is_sha256(text):
        raise ValueError(
            f"stage179_submit_authorization_{field_name}_invalid"
        )
    return text


def _normalized_int(value: Any, *, field_name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
            f"stage179_submit_authorization_{field_name}_invalid"
        )
    return value


def _artifact_int(value: Any, *, minimum: int = 0) -> int | None:
    if type(value) is not int or value < minimum:
        return None
    return value


def _normalized_authorized_intents(
    rows: Any,
    *,
    authorization_lane: str | None = None,
    intent_scope: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError(
            "stage179_submit_authorization_authorized_intents_missing"
        )
    normalized: list[dict[str, Any]] = []
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
        if not _is_sha256(payload_sha256):
            raise ValueError(
                "stage179_submit_authorization_payload_sha256_invalid"
            )
        if intent_kind not in _INTENT_KINDS:
            raise ValueError(
                "stage179_submit_authorization_intent_kind_invalid"
            )
        seen.add(intent_id)
        normalized_row: dict[str, Any] = {
            "intent_id": intent_id,
            "payload_sha256": payload_sha256,
            "intent_kind": intent_kind,
        }
        for field_name in _EXACT_TEXT_FIELDS:
            if field_name not in row:
                continue
            text = str(row.get(field_name, "")).strip()
            if not text:
                raise ValueError(
                    "stage179_submit_authorization_"
                    f"authorized_intent_{field_name}_invalid"
                )
            normalized_row[field_name] = text
        for field_name in _EXACT_INT_FIELDS:
            if field_name not in row:
                continue
            minimum = 1 if field_name in {"spool_sequence", "deadline_epoch_ns"} else 0
            normalized_row[field_name] = _normalized_int(
                row.get(field_name),
                field_name=f"authorized_intent_{field_name}",
                minimum=minimum,
            )
        normalized.append(normalized_row)
    if authorization_lane in {
        "persistent_intraday_fast",
        "session_initial_open",
    }:
        if len(normalized) != 1:
            raise ValueError(
                "stage179_submit_authorization_fast_lane_exactly_one_intent_required"
                if authorization_lane == "persistent_intraday_fast"
                else "stage179_submit_authorization_initial_open_lane_exactly_one_intent_required"
            )
        expected_scopes = (
            {"reduce_close_only", "retry_open_only"}
            if authorization_lane == "persistent_intraday_fast"
            else {"initial_open_only"}
        )
        if intent_scope not in expected_scopes:
            raise ValueError(
                "stage179_submit_authorization_fast_lane_scope_invalid"
                if authorization_lane == "persistent_intraday_fast"
                else "stage179_submit_authorization_initial_open_lane_scope_invalid"
            )
        row = normalized[0]
        missing = [
            field_name
            for field_name in (*_EXACT_TEXT_FIELDS, *_EXACT_INT_FIELDS)
            if field_name not in row
        ]
        if missing:
            raise ValueError(
                "stage179_submit_authorization_fast_lane_exact_identity_missing:"
                + ",".join(missing)
            )
        if authorization_lane == "session_initial_open":
            if row["intent_kind"] != "open":
                raise ValueError(
                    "stage179_submit_authorization_initial_open_scope_contains_non_open"
                )
            if (
                row["source"] != _INITIAL_OPEN_SOURCE
                or row["intent_role"] != _INITIAL_OPEN_ROLE
            ):
                raise ValueError(
                    "stage179_submit_authorization_initial_open_source_role_invalid"
                )
        elif intent_scope == "reduce_close_only":
            if row["intent_kind"] != "close":
                raise ValueError(
                    "stage179_submit_authorization_reduce_close_scope_contains_open"
                )
            if (
                row["source"] != _FAST_CLOSE_SOURCE
                or row["intent_role"] not in _FAST_CLOSE_ROLES
            ):
                raise ValueError(
                    "stage179_submit_authorization_fast_close_source_role_invalid"
                )
        else:
            if row["intent_kind"] != "open":
                raise ValueError(
                    "stage179_submit_authorization_retry_open_scope_contains_close"
                )
            if (
                row["source"] != _FAST_RETRY_OPEN_SOURCE
                or row["intent_role"] != _FAST_RETRY_OPEN_ROLE
            ):
                raise ValueError(
                    "stage179_submit_authorization_fast_retry_open_source_role_invalid"
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
    authorization_lane: str = "slow_controller",
    spool_path: str | Path = "",
    spool_snapshot_digest: str = "",
    cursor_digest: str = "",
    stage902_evidence_digest: str = "",
    stage927_evidence_digest: str = "",
) -> dict[str, Any]:
    """Publish one canonical v4 admission record.

    ``slow_controller`` keeps the legacy controller evidence contract.
    ``persistent_intraday_fast`` and ``session_initial_open`` are intentionally
    narrow: exactly one whitelisted row, a scope-specific permit, and complete
    spool/gate digests are mandatory.
    """

    authorization_lane = str(authorization_lane).strip()
    if authorization_lane not in _AUTHORIZATION_LANES:
        raise ValueError(
            "stage179_submit_authorization_authorization_lane_invalid"
        )
    if intent_scope not in _INTENT_SCOPES:
        raise ValueError("stage179_submit_authorization_intent_scope_invalid")
    issued_epoch_ns = _normalized_int(
        issued_epoch_ns,
        field_name="issued_epoch_ns",
        minimum=1,
    )
    expires_epoch_ns = _normalized_int(
        expires_epoch_ns,
        field_name="expires_epoch_ns",
        minimum=1,
    )
    if expires_epoch_ns <= issued_epoch_ns:
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
    normalized_intents = _normalized_authorized_intents(
        authorized_intents,
        authorization_lane=authorization_lane,
        intent_scope=intent_scope,
    )
    if intent_scope == "reduce_close_only" and any(
        row["intent_kind"] != "close" for row in normalized_intents
    ):
        raise ValueError(
            "stage179_submit_authorization_reduce_close_scope_contains_open"
        )
    if intent_scope == "retry_open_only" and any(
        row["intent_kind"] != "open" for row in normalized_intents
    ):
        raise ValueError(
            "stage179_submit_authorization_retry_open_scope_contains_close"
        )
    if intent_scope == "initial_open_only" and any(
        row["intent_kind"] != "open" for row in normalized_intents
    ):
        raise ValueError(
            "stage179_submit_authorization_initial_open_scope_contains_non_open"
        )
    for row in normalized_intents:
        deadline_epoch_ns = row.get("deadline_epoch_ns")
        if (
            isinstance(deadline_epoch_ns, int)
            and expires_epoch_ns > deadline_epoch_ns
        ):
            raise ValueError(
                "stage179_submit_authorization_exceeds_intent_deadline"
            )
    normalized_spool_path = str(spool_path or "").strip()
    if normalized_spool_path:
        normalized_spool_path = str(
            Path(normalized_spool_path).expanduser().resolve(strict=False)
        )
    binding_digests = {
        "spool_snapshot_digest": _optional_digest(
            spool_snapshot_digest,
            field_name="spool_snapshot_digest",
        ),
        "cursor_digest": _optional_digest(
            cursor_digest,
            field_name="cursor_digest",
        ),
        "stage902_evidence_digest": _optional_digest(
            stage902_evidence_digest,
            field_name="stage902_evidence_digest",
        ),
        "stage927_evidence_digest": _optional_digest(
            stage927_evidence_digest,
            field_name="stage927_evidence_digest",
        ),
    }
    if authorization_lane in {
        "persistent_intraday_fast",
        "session_initial_open",
    }:
        if not normalized_spool_path:
            raise ValueError(
                "stage179_submit_authorization_fast_lane_spool_path_missing"
                if authorization_lane == "persistent_intraday_fast"
                else "stage179_submit_authorization_initial_open_lane_spool_path_missing"
            )
        missing_digests = [
            key for key, value in binding_digests.items() if not value
        ]
        if missing_digests:
            raise ValueError(
                (
                    "stage179_submit_authorization_fast_lane_binding_digest_missing:"
                    if authorization_lane == "persistent_intraday_fast"
                    else "stage179_submit_authorization_initial_open_lane_binding_digest_missing:"
                )
                + ",".join(missing_digests)
            )
    payload = _signed(
        {
            "schema_version": SUBMIT_AUTHORIZATION_SCHEMA_VERSION,
            "status": "authorized",
            **{key: str(value).strip() for key, value in required_strings.items()},
            "authorization_lane": authorization_lane,
            "intent_scope": intent_scope,
            "authorized_intents": normalized_intents,
            "issued_epoch_ns": issued_epoch_ns,
            "expires_epoch_ns": expires_epoch_ns,
            "spool_path": normalized_spool_path,
            **binding_digests,
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
    revoked_epoch_ns = _normalized_int(
        revoked_epoch_ns,
        field_name="revoked_epoch_ns",
        minimum=1,
    )
    authorization_path = Path(path).expanduser().resolve(strict=False)
    previous: dict[str, Any] = {}
    try:
        loaded = json.loads(authorization_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            previous = loaded
    except (OSError, ValueError, TypeError):
        pass
    previous_expiry = _artifact_int(
        previous.get("expires_epoch_ns"),
        minimum=1,
    )
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
            "revoked_epoch_ns": revoked_epoch_ns,
            "expires_epoch_ns": min(
                previous_expiry or revoked_epoch_ns,
                revoked_epoch_ns,
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


def _authorized_rows_from_payload(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    lane = str(payload.get("authorization_lane", ""))
    scope = str(payload.get("intent_scope", ""))
    if lane not in _AUTHORIZATION_LANES or scope not in _INTENT_SCOPES:
        raise ValueError("authorization_identity_invalid")
    if lane in {"persistent_intraday_fast", "session_initial_open"}:
        expected_scopes = (
            {"reduce_close_only", "retry_open_only"}
            if lane == "persistent_intraday_fast"
            else {"initial_open_only"}
        )
        if scope not in expected_scopes:
            raise ValueError("authorization_exact_lane_scope_invalid")
        spool_path = str(payload.get("spool_path", "")).strip()
        if not spool_path or not Path(spool_path).is_absolute():
            raise ValueError("authorization_exact_lane_spool_path_invalid")
        for field_name in (
            "spool_snapshot_digest",
            "cursor_digest",
            "stage902_evidence_digest",
            "stage927_evidence_digest",
        ):
            if not _is_sha256(payload.get(field_name, "")):
                raise ValueError("authorization_exact_lane_digest_invalid")
    rows = _normalized_authorized_intents(
        payload.get("authorized_intents"),
        authorization_lane=lane,
        intent_scope=scope,
    )
    if scope == "reduce_close_only" and any(
        row["intent_kind"] != "close" for row in rows
    ):
        raise ValueError("authorization_reduce_close_scope_invalid")
    if scope == "retry_open_only" and any(
        row["intent_kind"] != "open" for row in rows
    ):
        raise ValueError("authorization_retry_open_scope_invalid")
    if scope == "initial_open_only" and any(
        row["intent_kind"] != "open" for row in rows
    ):
        raise ValueError("authorization_initial_open_scope_invalid")
    return rows


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
        rows = _authorized_rows_from_payload(payload)
    except ValueError:
        return {}
    return {row["intent_id"]: row["payload_sha256"] for row in rows}


def authorized_submit_intent_records(
    path: str | Path,
) -> list[dict[str, Any]]:
    """Return canonical v4 records, or no authority on any artifact defect."""

    payload = read_submit_authorization(path)
    if (
        payload.get("schema_version") != SUBMIT_AUTHORIZATION_SCHEMA_VERSION
        or payload.get("status") != "authorized"
    ):
        return []
    digest = str(payload.get("record_digest", ""))
    if not _is_sha256(digest) or not hmac.compare_digest(
        digest,
        _canonical_digest(payload),
    ):
        return []
    try:
        return _authorized_rows_from_payload(payload)
    except ValueError:
        return []


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
    authorization_lane: str | None = None,
    intent_scope: str | None = None,
    source: str | None = None,
    intent_role: str | None = None,
    trace_id: str | None = None,
    spool_sequence: int | None = None,
    state_revision: int | None = None,
    state_generation: str | None = None,
    position_epoch_id: str | None = None,
    root_position_id: str | None = None,
    position_cycle_id: str | None = None,
    deadline_epoch_ns: int | None = None,
    spool_path: str | Path | None = None,
    spool_snapshot_digest: str | None = None,
    cursor_digest: str | None = None,
    stage902_evidence_digest: str | None = None,
    stage927_evidence_digest: str | None = None,
    allow_expired_if_record_digest: str | None = None,
) -> list[str]:
    """Return every fail-closed blocker for one authorization boundary.

    For a fast-lane leased row, ``state_revision`` denotes the authorized
    *ready* revision.  ``lease_next`` increments that revision, so the caller
    must separately prove ``leased_revision == authorized_revision + 1``.
    ``allow_expired_if_record_digest`` only waives admission/evidence lease
    expiry for the exact record digest pinned after a successful lease check;
    status, identity, scope, digests, broker generations, and intent deadline
    remain enforced.
    """

    payload = read_submit_authorization(path)
    if not payload:
        return ["stage179_submit_authorization_missing"]
    blockers: list[str] = []
    normalized_now_epoch_ns = _artifact_int(now_epoch_ns, minimum=0)
    if normalized_now_epoch_ns is None:
        return ["stage179_submit_authorization_now_epoch_ns_invalid"]
    schema_valid = (
        payload.get("schema_version") == SUBMIT_AUTHORIZATION_SCHEMA_VERSION
    )
    if not schema_valid:
        blockers.append("stage179_submit_authorization_schema_invalid")
    digest = str(payload.get("record_digest", ""))
    digest_valid = bool(
        _is_sha256(digest)
        and hmac.compare_digest(digest, _canonical_digest(payload))
    )
    if not digest_valid:
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
    pinned_digest_matches = False
    if allow_expired_if_record_digest is not None:
        pinned_digest = str(allow_expired_if_record_digest).strip().lower()
        if not _is_sha256(pinned_digest) or not (
            schema_valid
            and digest_valid
            and hmac.compare_digest(pinned_digest, digest)
        ):
            blockers.append(
                "stage179_submit_authorization_pinned_record_digest_mismatch"
            )
        elif intent_id is None or payload_sha256 is None:
            blockers.append(
                "stage179_submit_authorization_pinned_intent_identity_missing"
            )
        else:
            pinned_digest_matches = True
    issued_epoch_ns = _artifact_int(
        payload.get("issued_epoch_ns"),
        minimum=1,
    )
    authorization_expires_epoch_ns = _artifact_int(
        payload.get("expires_epoch_ns"),
        minimum=1,
    )
    if issued_epoch_ns is None:
        blockers.append("stage179_submit_authorization_issued_time_invalid")
    if authorization_expires_epoch_ns is None:
        blockers.append("stage179_submit_authorization_expiry_invalid")
    elif (
        issued_epoch_ns is not None
        and authorization_expires_epoch_ns <= issued_epoch_ns
    ):
        blockers.append("stage179_submit_authorization_expiry_invalid")
    elif (
        not pinned_digest_matches
        and normalized_now_epoch_ns >= authorization_expires_epoch_ns
    ):
        blockers.append("stage179_submit_authorization_expired")
    if not str(payload.get("cycle_id", "")).strip():
        blockers.append("stage179_submit_authorization_cycle_id_missing")
    lane = str(payload.get("authorization_lane", ""))
    if lane not in _AUTHORIZATION_LANES:
        blockers.append(
            "stage179_submit_authorization_authorization_lane_invalid"
        )
    if (
        authorization_lane is not None
        and lane != str(authorization_lane).strip()
    ):
        blockers.append(
            "stage179_submit_authorization_authorization_lane_mismatch"
        )
    scope = str(payload.get("intent_scope", ""))
    if scope not in _INTENT_SCOPES:
        blockers.append("stage179_submit_authorization_intent_scope_invalid")
    if intent_scope is not None and scope != str(intent_scope).strip():
        blockers.append(
            "stage179_submit_authorization_intent_scope_mismatch"
        )
    if lane == "persistent_intraday_fast" and scope not in {
        "reduce_close_only",
        "retry_open_only",
    }:
        blockers.append(
            "stage179_submit_authorization_fast_lane_scope_invalid"
        )
    if lane == "session_initial_open" and scope != "initial_open_only":
        blockers.append(
            "stage179_submit_authorization_initial_open_lane_scope_invalid"
        )
    authorized_rows: list[dict[str, Any]] = []
    try:
        authorized_rows = _normalized_authorized_intents(
            payload.get("authorized_intents"),
            authorization_lane=lane,
            intent_scope=scope,
        )
    except ValueError as exc:
        blockers.append(str(exc))
    if any(
        isinstance(row.get("deadline_epoch_ns"), int)
        and normalized_now_epoch_ns >= int(row["deadline_epoch_ns"])
        for row in authorized_rows
    ):
        blockers.append(
            "stage179_submit_authorization_intent_deadline_expired"
        )
    if (
        authorization_expires_epoch_ns is not None
        and any(
            isinstance(row.get("deadline_epoch_ns"), int)
            and authorization_expires_epoch_ns > int(row["deadline_epoch_ns"])
            for row in authorized_rows
        )
    ):
        blockers.append(
            "stage179_submit_authorization_exceeds_intent_deadline"
        )
    for evidence_key in (
        "controller_evidence",
        "stage927_evidence",
        "broker_gate_evidence",
        "tick_watermark_evidence",
    ):
        if not isinstance(payload.get(evidence_key), dict) or not payload[evidence_key]:
            blockers.append(f"stage179_submit_authorization_{evidence_key}_missing")
    stored_spool_path = str(payload.get("spool_path", "")).strip()
    if stored_spool_path:
        stored_spool_path = str(
            Path(stored_spool_path).expanduser().resolve(strict=False)
        )
    exact_lane = lane in {
        "persistent_intraday_fast",
        "session_initial_open",
    }
    if exact_lane and not stored_spool_path:
        blockers.append(
            "stage179_submit_authorization_exact_lane_spool_path_missing"
        )
    if spool_path is not None:
        expected_spool_path = str(
            Path(spool_path).expanduser().resolve(strict=False)
        )
        if stored_spool_path != expected_spool_path:
            blockers.append(
                "stage179_submit_authorization_spool_path_mismatch"
            )
    binding_digest_expectations = {
        "spool_snapshot_digest": spool_snapshot_digest,
        "cursor_digest": cursor_digest,
        "stage902_evidence_digest": stage902_evidence_digest,
        "stage927_evidence_digest": stage927_evidence_digest,
    }
    for field_name, expected_digest in binding_digest_expectations.items():
        stored_digest = str(payload.get(field_name, "")).strip().lower()
        if stored_digest and not _is_sha256(stored_digest):
            blockers.append(
                f"stage179_submit_authorization_{field_name}_invalid"
            )
        if exact_lane and not stored_digest:
            blockers.append(
                "stage179_submit_authorization_exact_lane_"
                f"{field_name}_missing"
            )
        if expected_digest is not None:
            normalized_expected = str(expected_digest).strip().lower()
            if not _is_sha256(normalized_expected):
                blockers.append(
                    "stage179_submit_authorization_expected_"
                    f"{field_name}_invalid"
                )
            elif not _is_sha256(stored_digest) or not hmac.compare_digest(
                stored_digest,
                normalized_expected,
            ):
                blockers.append(
                    f"stage179_submit_authorization_{field_name}_mismatch"
                )
    if scope == "reduce_close_only":
        if intent_kind is not None and str(intent_kind).lower() != "close":
            blockers.append("stage179_submit_authorization_reduce_close_only")
        if child_offset is not None and str(child_offset).lower() == "open":
            blockers.append("stage179_submit_authorization_reduce_close_only")
    elif scope == "retry_open_only":
        if intent_kind is not None and str(intent_kind).lower() != "open":
            blockers.append("stage179_submit_authorization_retry_open_only")
        if child_offset is not None and str(child_offset).lower() != "open":
            blockers.append("stage179_submit_authorization_retry_open_only")
    elif scope == "initial_open_only":
        if intent_kind is not None and str(intent_kind).lower() != "open":
            blockers.append("stage179_submit_authorization_initial_open_only")
        if child_offset is not None and str(child_offset).lower() != "open":
            blockers.append("stage179_submit_authorization_initial_open_only")
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
            exact_expectations: dict[str, Any] = {
                "source": source,
                "intent_role": intent_role,
                "trace_id": trace_id,
                "spool_sequence": spool_sequence,
                "state_revision": state_revision,
                "state_generation": state_generation,
                "position_epoch_id": position_epoch_id,
                "root_position_id": root_position_id,
                "position_cycle_id": position_cycle_id,
                "deadline_epoch_ns": deadline_epoch_ns,
            }
            if exact_lane:
                missing_expected = [
                    field_name
                    for field_name, expected_value in exact_expectations.items()
                    if expected_value is None
                ]
                if missing_expected:
                    blockers.append(
                        "stage179_submit_authorization_exact_lane_"
                        "expected_exact_identity_missing:"
                        + ",".join(missing_expected)
                    )
            for field_name, expected_value in exact_expectations.items():
                if expected_value is None:
                    continue
                if field_name in _EXACT_INT_FIELDS:
                    minimum = (
                        1
                        if field_name in {"spool_sequence", "deadline_epoch_ns"}
                        else 0
                    )
                    try:
                        normalized_expected: Any = _normalized_int(
                            expected_value,
                            field_name=f"expected_{field_name}",
                            minimum=minimum,
                        )
                    except ValueError as exc:
                        blockers.append(str(exc))
                        continue
                else:
                    normalized_expected = str(expected_value).strip()
                    if not normalized_expected:
                        blockers.append(
                            "stage179_submit_authorization_expected_"
                            f"{field_name}_invalid"
                        )
                        continue
                if authorized.get(field_name) != normalized_expected:
                    blockers.append(
                        "stage179_submit_authorization_authorized_intent_"
                        f"{field_name}_mismatch"
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
    for evidence_name, evidence_payload in evidence_expiry_keys:
        evidence_expires_epoch_ns = (
            _artifact_int(
                evidence_payload.get("expires_epoch_ns"),
                minimum=1,
            )
            if isinstance(evidence_payload, dict)
            else None
        )
        if evidence_expires_epoch_ns is None:
            blockers.append(
                "stage179_submit_authorization_"
                f"{evidence_name}_expiry_missing"
            )
            continue
        if (
            authorization_expires_epoch_ns is not None
            and authorization_expires_epoch_ns > evidence_expires_epoch_ns
        ):
            blockers.append(
                "stage179_submit_authorization_"
                f"exceeds_{evidence_name}_expiry"
            )
        if (
            not pinned_digest_matches
            and normalized_now_epoch_ns >= evidence_expires_epoch_ns
        ):
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
        if lane == "persistent_intraday_fast":
            if (
                controller.get("controller_status")
                != "persistent_intraday_fast_ready"
            ):
                blockers.append(
                    "stage179_submit_authorization_fast_controller_not_ready"
                )
        elif lane == "session_initial_open":
            if (
                controller.get("controller_status")
                != "session_initial_open_prearmed_ready"
            ):
                blockers.append(
                    "stage179_submit_authorization_initial_open_controller_not_ready"
                )
        else:
            if (
                not reduce_close_only
                and controller.get("controller_status")
                != "phase_d_controller_live_real_ready_no_submit_step"
            ):
                blockers.append(
                    "stage179_submit_authorization_controller_not_ready"
                )
            if (
                controller.get("stage905_executor_status")
                != "executor_dry_run_ready"
            ):
                blockers.append(
                    "stage179_submit_authorization_stage905_executor_not_ready"
                )
            if _artifact_int(
                controller.get("stage905_blocked_count"),
                minimum=0,
            ) != 0:
                blockers.append(
                    "stage179_submit_authorization_stage905_blocked"
                )
            ready_count = _artifact_int(
                controller.get("stage905_ready_count"),
                minimum=0,
            )
            if ready_count is None or ready_count <= 0:
                blockers.append(
                    "stage179_submit_authorization_no_ready_intent"
                )
    if isinstance(stage927, dict):
        if lane == "persistent_intraday_fast":
            permit_field = (
                "reduce_close_submit_permitted"
                if scope == "reduce_close_only"
                else "retry_open_submit_permitted"
            )
            if _artifact_int(stage927.get(permit_field), minimum=0) != 1:
                blockers.append(
                    "stage179_submit_authorization_stage927_"
                    f"{permit_field}_not_ready"
                )
        elif lane == "session_initial_open":
            if _artifact_int(
                stage927.get("initial_open_submit_permitted"),
                minimum=0,
            ) != 1:
                blockers.append(
                    "stage179_submit_authorization_stage927_"
                    "initial_open_submit_permitted_not_ready"
                )
        elif (
            not reduce_close_only
            and _artifact_int(
                stage927.get("real_submit_permitted"),
                minimum=0,
            )
            != 1
        ):
            blockers.append(
                "stage179_submit_authorization_stage927_not_ready"
            )
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
        broker_expires_epoch_ns = _artifact_int(
            broker.get("expires_epoch_ns"),
            minimum=1,
        )
        if broker_expires_epoch_ns is None:
            blockers.append(
                "stage179_submit_authorization_broker_readiness_expiry_missing"
            )
        else:
            if (
                authorization_expires_epoch_ns is not None
                and authorization_expires_epoch_ns > broker_expires_epoch_ns
            ):
                blockers.append(
                    "stage179_submit_authorization_exceeds_broker_readiness_expiry"
                )
            if (
                not pinned_digest_matches
                and normalized_now_epoch_ns >= broker_expires_epoch_ns
            ):
                blockers.append(
                    "stage179_submit_authorization_broker_readiness_expired"
                )
    if isinstance(tick, dict) and not reduce_close_only:
        all_symbols_ready = (
            _artifact_int(tick.get("all_symbols_ready"), minimum=0) == 1
        )
        candidate_symbol_ready = (
            bool(str(tick.get("candidate_symbol", "")).strip())
            and _artifact_int(
                tick.get("candidate_symbol_ready"),
                minimum=0,
            )
            == 1
            and _artifact_int(
                tick.get("candidate_ingress_epoch_ns"),
                minimum=1,
            )
            is not None
        )
        if not all_symbols_ready and not candidate_symbol_ready:
            blockers.append("stage179_submit_authorization_tick_gate_not_ready")
    return list(dict.fromkeys(blockers))


__all__ = [
    "SUBMIT_AUTHORIZATION_FILENAME",
    "SUBMIT_AUTHORIZATION_SCHEMA_VERSION",
    "authorized_submit_intent_records",
    "authorized_submit_intents",
    "publish_submit_authorization",
    "read_submit_authorization",
    "revoke_submit_authorization",
    "submit_authorization_path",
    "validate_submit_authorization",
]

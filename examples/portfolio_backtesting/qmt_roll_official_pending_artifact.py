from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any, Mapping

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_execution_profile import (
    OfficialExecutionProfile,
    assert_canonical_execution_profile,
    assert_profile_identity,
)


PENDING_ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_HASH_KEYS = (
    "official_summary",
    "signal_plan",
    "current_positions",
    "pending_orders",
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_REQUIRED_AUDIT_FIELDS = {
    "schema_version",
    "status",
    "cohort_id",
    "target_date",
    "execution_profile",
    "official_live_version",
    "capital",
    "capital_label",
    "official_summary_sha256",
    "signal_plan_sha256",
    "current_positions_sha256",
    "pending_orders_sha256",
    "pending_order_count",
    "order_api_called_count",
}
_PENDING_ROW_IDENTITY_FIELDS = (
    "cohort_id",
    "target_date",
    "execution_profile",
    "official_live_version",
    "capital",
    "capital_label",
)
_SNAPSHOT_SEAL = object()


@dataclass(frozen=True, slots=True, init=False)
class ValidatedArtifactSnapshot:
    _profile_key: str
    _artifact_paths: tuple[str, ...]
    _official_summary_bytes: bytes
    _signal_plan_bytes: bytes
    _current_positions_bytes: bytes
    _pending_orders_bytes: bytes
    _audit_bytes: bytes
    _seal: object


@dataclass(frozen=True, slots=True)
class MaterializedArtifactSnapshot:
    official_summary: dict[str, Any]
    signal_plan: pd.DataFrame
    current_positions: pd.DataFrame
    pending_orders: pd.DataFrame
    audit: dict[str, Any]
    artifact_hashes: dict[str, str]


def sha256_path(path: Path | str) -> str:
    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"pending_artifact_input_unreadable:{source}") from exc
    return hashlib.sha256(payload).hexdigest()


def artifact_hashes_for_profile(
    profile: OfficialExecutionProfile,
) -> dict[str, str]:
    return {
        "official_summary": sha256_path(profile.summary_path),
        "signal_plan": sha256_path(profile.signal_plan_path),
        "current_positions": sha256_path(profile.current_positions_path),
        "pending_orders": sha256_path(profile.pending_orders_path),
    }


def _parse_json_bytes(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        result = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"pending_artifact_{label}_unreadable") from exc
    if not isinstance(result, dict):
        raise ValueError(f"pending_artifact_{label}_invalid")
    return result


def _parse_csv_bytes(payload: bytes, *, label: str) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(payload), encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()
    except Exception as exc:
        raise ValueError(f"pending_artifact_{label}_unreadable") from exc


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def validate_pending_artifact_cohort(
    profile: OfficialExecutionProfile,
    *,
    target_date: str,
    pending_orders: pd.DataFrame,
    audit: Mapping[str, Any] | None,
    artifact_hashes: Mapping[str, str] | None,
) -> dict[str, Any]:
    if not isinstance(audit, Mapping):
        raise ValueError("pending_artifact_audit_missing")
    if not _REQUIRED_AUDIT_FIELDS.issubset(audit):
        raise ValueError("pending_artifact_audit_fields_missing")
    if audit.get("schema_version") != PENDING_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("pending_artifact_schema_mismatch")
    if audit.get("status") != "ready":
        raise ValueError("pending_artifact_not_ready")
    cohort_id = _clean(audit.get("cohort_id"))
    if not _valid_sha256(cohort_id):
        raise ValueError("pending_artifact_cohort_id_invalid")
    if _clean(audit.get("target_date")) != target_date:
        raise ValueError("pending_artifact_target_date_mismatch")
    if _clean(audit.get("execution_profile")) != profile.profile_key:
        raise ValueError("pending_artifact_execution_profile_mismatch")
    assert_profile_identity(
        profile,
        official_version=audit.get("official_live_version"),
        capital=audit.get("capital"),
        capital_label=audit.get("capital_label"),
    )
    if int(pd.to_numeric(audit.get("order_api_called_count"), errors="coerce")) != 0:
        raise ValueError("pending_artifact_order_api_count_nonzero")
    if int(pd.to_numeric(audit.get("pending_order_count"), errors="coerce")) != len(
        pending_orders
    ):
        raise ValueError("pending_artifact_order_count_mismatch")
    if not isinstance(artifact_hashes, Mapping):
        raise ValueError("pending_artifact_hashes_missing")
    for key in ARTIFACT_HASH_KEYS:
        observed = artifact_hashes.get(key)
        expected = audit.get(f"{key}_sha256")
        if not _valid_sha256(observed) or not _valid_sha256(expected):
            raise ValueError(f"pending_artifact_{key}_sha256_invalid")
        if observed != expected:
            raise ValueError(f"pending_artifact_{key}_sha256_mismatch")

    if not pending_orders.empty:
        missing_columns = set(_PENDING_ROW_IDENTITY_FIELDS).difference(
            pending_orders.columns
        )
        if missing_columns:
            raise ValueError("pending_artifact_row_identity_missing")
        expected_text = {
            "cohort_id": cohort_id,
            "target_date": target_date,
            "execution_profile": profile.profile_key,
            "official_live_version": profile.official_version,
            "capital_label": profile.capital_label,
        }
        for field, expected in expected_text.items():
            if any(_clean(value) != expected for value in pending_orders[field]):
                raise ValueError(f"pending_artifact_row_{field}_mismatch")
        capitals = pd.to_numeric(pending_orders["capital"], errors="coerce")
        if capitals.isna().any() or not capitals.eq(float(profile.capital)).all():
            raise ValueError("pending_artifact_row_capital_mismatch")
    return dict(audit)


def _materialize_snapshot_bytes(
    profile: OfficialExecutionProfile,
    *,
    official_summary_bytes: bytes,
    signal_plan_bytes: bytes,
    current_positions_bytes: bytes,
    pending_orders_bytes: bytes,
    audit_bytes: bytes,
) -> MaterializedArtifactSnapshot:
    official_summary = _parse_json_bytes(
        official_summary_bytes,
        label="official_summary",
    )
    signal_plan = _parse_csv_bytes(signal_plan_bytes, label="signal_plan")
    current_positions = _parse_csv_bytes(
        current_positions_bytes,
        label="current_positions",
    )
    pending_orders = _parse_csv_bytes(
        pending_orders_bytes,
        label="pending_orders",
    )
    audit = _parse_json_bytes(audit_bytes, label="audit")
    artifact_hashes = {
        "official_summary": hashlib.sha256(
            official_summary_bytes
        ).hexdigest(),
        "signal_plan": hashlib.sha256(signal_plan_bytes).hexdigest(),
        "current_positions": hashlib.sha256(
            current_positions_bytes
        ).hexdigest(),
        "pending_orders": hashlib.sha256(pending_orders_bytes).hexdigest(),
    }
    target_date = _clean(official_summary.get("analysis_end"))
    if not target_date:
        raise ValueError("official_summary_analysis_end_missing")
    validate_pending_artifact_cohort(
        profile,
        target_date=target_date,
        pending_orders=pending_orders,
        audit=audit,
        artifact_hashes=artifact_hashes,
    )
    return MaterializedArtifactSnapshot(
        official_summary=official_summary,
        signal_plan=signal_plan,
        current_positions=current_positions,
        pending_orders=pending_orders,
        audit=audit,
        artifact_hashes=artifact_hashes,
    )


def _profile_artifact_paths(
    profile: OfficialExecutionProfile,
) -> tuple[str, ...]:
    return tuple(
        str(path.resolve(strict=False))
        for path in (
            profile.summary_path,
            profile.signal_plan_path,
            profile.current_positions_path,
            profile.pending_orders_path,
            profile.pending_orders_audit_path,
        )
    )


def _build_validated_artifact_snapshot(
    profile: OfficialExecutionProfile,
    *,
    official_summary_bytes: bytes,
    signal_plan_bytes: bytes,
    current_positions_bytes: bytes,
    pending_orders_bytes: bytes,
    audit_bytes: bytes,
) -> ValidatedArtifactSnapshot:
    payloads = (
        official_summary_bytes,
        signal_plan_bytes,
        current_positions_bytes,
        pending_orders_bytes,
        audit_bytes,
    )
    if any(not isinstance(payload, bytes) for payload in payloads):
        raise ValueError("pending_artifact_snapshot_bytes_required")
    _materialize_snapshot_bytes(
        profile,
        official_summary_bytes=official_summary_bytes,
        signal_plan_bytes=signal_plan_bytes,
        current_positions_bytes=current_positions_bytes,
        pending_orders_bytes=pending_orders_bytes,
        audit_bytes=audit_bytes,
    )
    snapshot = object.__new__(ValidatedArtifactSnapshot)
    object.__setattr__(snapshot, "_profile_key", profile.profile_key)
    object.__setattr__(
        snapshot,
        "_artifact_paths",
        _profile_artifact_paths(profile),
    )
    object.__setattr__(
        snapshot,
        "_official_summary_bytes",
        bytes(official_summary_bytes),
    )
    object.__setattr__(
        snapshot,
        "_signal_plan_bytes",
        bytes(signal_plan_bytes),
    )
    object.__setattr__(
        snapshot,
        "_current_positions_bytes",
        bytes(current_positions_bytes),
    )
    object.__setattr__(
        snapshot,
        "_pending_orders_bytes",
        bytes(pending_orders_bytes),
    )
    object.__setattr__(snapshot, "_audit_bytes", bytes(audit_bytes))
    object.__setattr__(snapshot, "_seal", _SNAPSHOT_SEAL)
    return snapshot


def load_validated_artifact_snapshot(
    profile: OfficialExecutionProfile,
) -> ValidatedArtifactSnapshot:
    assert_canonical_execution_profile(profile)
    try:
        audit_before = profile.pending_orders_audit_path.read_bytes()
        official_summary_bytes = profile.summary_path.read_bytes()
        signal_plan_bytes = profile.signal_plan_path.read_bytes()
        current_positions_bytes = profile.current_positions_path.read_bytes()
        pending_orders_bytes = profile.pending_orders_path.read_bytes()
        audit_after = profile.pending_orders_audit_path.read_bytes()
    except OSError as exc:
        raise ValueError("pending_artifact_snapshot_read_failed") from exc
    if audit_before != audit_after:
        raise ValueError("pending_artifact_snapshot_generation_changed")
    return _build_validated_artifact_snapshot(
        profile,
        official_summary_bytes=official_summary_bytes,
        signal_plan_bytes=signal_plan_bytes,
        current_positions_bytes=current_positions_bytes,
        pending_orders_bytes=pending_orders_bytes,
        audit_bytes=audit_after,
    )


def materialize_validated_artifact_snapshot(
    profile: OfficialExecutionProfile,
    snapshot: ValidatedArtifactSnapshot | None,
) -> MaterializedArtifactSnapshot:
    assert_canonical_execution_profile(profile)
    if (
        not isinstance(snapshot, ValidatedArtifactSnapshot)
        or snapshot._seal is not _SNAPSHOT_SEAL
    ):
        raise ValueError("pending_artifact_validated_snapshot_required")
    if snapshot._profile_key != profile.profile_key:
        raise ValueError("pending_artifact_snapshot_profile_mismatch")
    if snapshot._artifact_paths != _profile_artifact_paths(profile):
        raise ValueError("pending_artifact_snapshot_paths_mismatch")
    return _materialize_snapshot_bytes(
        profile,
        official_summary_bytes=snapshot._official_summary_bytes,
        signal_plan_bytes=snapshot._signal_plan_bytes,
        current_positions_bytes=snapshot._current_positions_bytes,
        pending_orders_bytes=snapshot._pending_orders_bytes,
        audit_bytes=snapshot._audit_bytes,
    )

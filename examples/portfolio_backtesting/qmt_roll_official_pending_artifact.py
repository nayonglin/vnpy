from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Mapping

import pandas as pd

from qmt_roll_official_execution_profile import (
    OfficialExecutionProfile,
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
